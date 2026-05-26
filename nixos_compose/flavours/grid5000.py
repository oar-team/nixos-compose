import json
import os
import os.path as op
import socket
import subprocess
import sys
import time
from string import Template

import click

from ..actions import (
    generate_deploy_info_b64,
    generate_deployment_info,
    generate_kexec_scripts,
    get_machine_from_file,
    launch_ssh_kexec,
    read_compose_info,
    realpath_from_store_remote,
    ssh_connect,
    wait_ssh_ports,
)
from ..driver.machine import Machine
from ..flavour import Flavour

# from ..driver.logger import rootlog

KADEPLOY_ARCH = {
    "x86_64-linux": "x86_64",
    "powerpc64le-linux": "ppc64le",
    "aarch64-linux": "aarch64",
}

KADEPLOY_ENV_DESC = """
      name: $image_name
      version: 1
      description: NixOS
      author: $author
      visibility: shared
      destructive: false
      os: linux
      arch: $system
      image:
        file: $file_image_url
        kind: tar
        compression: xz
      boot:
        kernel: /boot/bzImage
        initrd: /boot/initrd
        kernel_params: $kernel_params
      filesystem: ext4
      partition_type: 131
      multipart: false
"""


def generate_kadeploy_envfile(
    ctx, deploy=None, kernel_params="", kaenv_path=None, deploy_image_path=None
):
    if not ctx.compose_info:
        read_compose_info(ctx)

    base_path = op.join(
        ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
    )
    os.makedirs(base_path, mode=0o700, exist_ok=True)
    if kaenv_path is None:
        kaenv_path = op.join(base_path, "nixos.yaml")

    if not deploy:
        if ctx.use_httpd:
            base_url = f"http://{ctx.httpd.ip}:{ctx.httpd.port}"
            deploy = f"{base_url}/deploy/{ctx.composition_flavour_prefix}.json"
        else:
            generate_deploy_info_b64(ctx)
            deploy = ctx.deployment_info_b64

    user = os.environ["USER"]

    fqdn = socket.getfqdn()
    g5k_site = fqdn.split(".")[1]

    system = ctx.compositions_info["system"]
    additional_kernel_params = ""
    if ctx.kernel_params:
        additional_kernel_params = ctx.kernel_params
    with open(kaenv_path, "w") as kaenv_file:
        t = Template(KADEPLOY_ENV_DESC)
        kaenv = t.substitute(
            image_name="NixOS",
            author=user,
            system=KADEPLOY_ARCH[system],
            file_image_url=f"local://{deploy_image_path}"
            if deploy_image_path
            else f"http://public.{g5k_site}.grid5000.fr/~{user}/nixos.tar.xz",
            kernel_params=f"boot.shell_on_fail console=tty0 console=ttyS0,115200 check_kernel_initrd deploy={deploy} {additional_kernel_params} {kernel_params}",
        )
        kaenv_file.write(kaenv)


def generate_machine_file_retrieve_ips(ctx):
    if not ctx.machine_file:
        fqdn = socket.getfqdn()
        g5k_site = fqdn.split(".")[1]
        g5k_frontend = "f" + g5k_site
        if g5k_frontend != socket.gethostname():
            output = subprocess.check_output([
                "ssh",
                g5k_frontend,
                "oarstat -u -J",
            ]).decode()
        else:
            output = subprocess.check_output(["oarstat", "-u", "-J"]).decode()
        oarstat_json = json.loads(output)

        job_id = 0
        nb_nodes = 0
        for jid, j in oarstat_json.items():
            if "deploy" in j["types"]:
                try:
                    os.remove(".oar_nodefile")
                except OSError:
                    pass
                with open(".oar_nodefile", "w") as outfile:
                    for n in j["assigned_network_address"]:
                        outfile.write(n + "\n")
                        nb_nodes += 1
                        job_id = jid

                if nb_nodes > 0:
                    ctx.vlog(
                        f"Auto generate .oar_nodefile as a machine file from job: {job_id} with {nb_nodes} nodes identified"
                    )
                else:
                    ctx.elog(
                        "Cannot retrieve machines from existing deployed job, verify it exists or give a machine file"
                    )
                    sys.exit(1)
                ctx.machine_file = ctx.envdir + "/.oar_nodefile"
                break
    if not ctx.machine_file:
        ctx.elog(
            "Cannot retrieve machines from any existing jobs, verify if one exists or give a machine file"
        )
        sys.exit(1)
    get_machine_from_file(ctx)


class G5kFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        if ctx.ssh == "":
            ctx.ssh = "ssh -l root"

    def generate_deployment_info(self, ssh_pub_key_file=None):
        if self.ctx.ip_addresses == []:
            generate_machine_file_retrieve_ips(self.ctx)
        generate_deployment_info(self.ctx, ssh_pub_key_file)


class G5kKexecBasedFlavour(G5kFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)

    def generate_kexec_scripts(self):
        generate_kexec_scripts(self.ctx)

    def launch(self):
        if "no-launch" in self.ctx.start_option:
            self.ctx.vlog("Start option no-launch, exit now without launching kexec")
            sys.exit(0)
        launch_ssh_kexec(self.ctx)
        time.sleep(10)
        wait_ssh_ports(self.ctx)

    def driver_initialize(self, tmp_dir):
        self.tmp_dir = tmp_dir
        ctx = self.ctx

        if ctx.no_start:
            deployment_nodes = self.ctx.deployment_info["deployment"]
            for ip, node in deployment_nodes.items():
                self.machines.append(
                    Machine(
                        self.ctx,
                        ip=ip,
                        tmp_dir=tmp_dir,
                        start_command="",
                        keep_vm_state=False,
                        name=node["host"],
                    )
                )

            for machine in self.machines:
                if not machine.connected:
                    self.start(machine)
                machine.connected = True
            return

    def start(self, machine):
        if not self.ctx.no_start:
            print("Not Yet Implemented")
            sys.exit(1)
        else:
            machine.start_process_shell([
                "ssh",
                "-t",
                "-o",
                "StrictHostKeyChecking=no",
                "-l",
                "root",
                machine.ip,
            ])

    def ext_connect(self, user, node, execute, ssh_key_file):
        return ssh_connect(self.ctx, user, node, execute, ssh_key_file)


class G5kNfsStoreFlavour(G5kKexecBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "g5k-nfs-store"

    def generate_kexec_scripts(self):
        def get_store_path():
            for prefix_store_path in self.ctx.alternative_stores + ["/nix"]:
                store_path = f"{prefix_store_path}/store"
                if op.exists(store_path):
                    return store_path
            self.ctx.elog("Store Path Not Found")
            sys.exit(1)

        if "NFS_STORE" in os.environ:
            nfs_store_str = os.environ["NFS_STORE"]
            nfs_store_parts = nfs_store_str.split(":")

            try:
                # use ip tp avoid potential issue during stage 1 on node if fqn is not used
                ip = socket.gethostbyname(nfs_store_parts[0])
            except ValueError:
                self.ctx.elog(
                    f"NFS_STORE environment variable is malformed {nfs_store_str}"
                )
                sys.exit(1)
            if len(nfs_store_parts) == 1:
                directory = "/nix/store"
            else:
                directory = nfs_store_parts[1]
            kernel_params = f"nfs_store={ip}:{directory}"
        else:
            nfs = socket.getfqdn("nfs")
            store_path = get_store_path()
            kernel_params = f"nfs_store={nfs}:/export{store_path}"
        self.ctx.vlog(f" kernel_params: {kernel_params}")

        generate_kexec_scripts(self.ctx, flavour_kernel_params=kernel_params)


class G5kRamdiskFlavour(G5kKexecBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "g5k-ramdisk"


class G5kImageFlavour(G5kFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "g5k-image"
        self.ask_before_kadeploy = True

    def launch(self, machine_file=None, kaenv_path=None, deploy_image_path=None):
        generate_kadeploy_envfile(
            self.ctx, kaenv_path=kaenv_path, deploy_image_path=deploy_image_path
        )

        remote_store_url = None
        if self.ctx.image_store_ssh:
            remote_store_url = f"ssh://{self.ctx.image_store_ssh}"
        image_path, use_image_store_ssh = realpath_from_store_remote(
            self.ctx, self.ctx.deployment_info["all"]["image"], remote_store_url
        )

        if deploy_image_path is None:
            user = os.environ["USER"]
            deploy_image_path = f"~{user}/public/nixos.tar.xz"

        if use_image_store_ssh:
            cmd_copy = "scp"
            image_path = f"{self.ctx.image_store_ssh}:{image_path}"
        else:
            cmd_copy = "cp"

        cmd_copy_image = f"{cmd_copy} {image_path} {deploy_image_path} && chmod 644 {deploy_image_path}"
        if (
            machine_file
            or self.ctx.machine_file
            or click.confirm(f"Do you want to copy image to {deploy_image_path} ?")
        ):
            try:
                subprocess.call(cmd_copy_image, shell=True)
            except Exception as ex:  # noqa: BLE001 - surface any copy failure as ClickException
                raise click.ClickException(f"Failed to copy image: {ex}")
        else:
            print(f"You can copy image with: {cmd_copy_image}")
        base_path = op.join(
            self.ctx.envdir,
            f"artifact/{self.ctx.composition_name}/{self.ctx.flavour.name}",
        )
        if kaenv_path is None:
            kaenv_path = op.join(base_path, "nixos.yaml")

        fqdn = socket.getfqdn()
        g5k_site = fqdn.split(".")[1]
        g5k_frontend = "f" + g5k_site

        ssh2frontend = ""
        if g5k_frontend != socket.gethostname():
            ssh2frontend = f"ssh {g5k_frontend} -t"

        cmd_kadeploy = (
            f"{ssh2frontend} kadeploy3 -a {kaenv_path} -f {self.ctx.machine_file}"
        )

        # g5k_frontend == socket.gethostname() and "OAR_NODEFILE" in os.environb:
        # cmd_kadeploy = f"kadeploy3 -a {kaenv_path} -f $OAR_NODEFILE"

        if not self.ask_before_kadeploy or click.confirm(
            f"Do you want to launch kadeploy: \n {cmd_kadeploy}"
        ):
            try:
                self.ctx.vlog(cmd_kadeploy)
                subprocess.call(cmd_kadeploy, shell=True)
            except Exception as ex:  # noqa: BLE001 - surface any kadeploy failure as ClickException
                raise click.ClickException(f"Failed to execute kadeploy command: {ex}")
        else:
            print(f"You can kadeploy image with: {cmd_kadeploy}")

    def start(self, machine):
        if not self.ctx.no_start:
            print("Not Yet Implemented")
            sys.exit(1)
        else:
            machine.start_process_shell([
                "ssh",
                "-t",
                "-o",
                "StrictHostKeyChecking=no",
                "-l",
                "root",
                machine.ip,
            ])

    def ext_connect(self, user, node, execute=True, ssh_key_file=None):
        return ssh_connect(self.ctx, user, node, execute, ssh_key_file)
