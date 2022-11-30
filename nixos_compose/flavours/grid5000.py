import os
import os.path as op
import time
from string import Template
import click
import subprocess
import socket

from ..flavour import Flavour
from ..actions import (
    read_compose_info,
    realpath_from_store,
    generate_deployment_info,
    generate_deploy_info_b64,
    generate_kexec_scripts,
    launch_ssh_kexec,
    wait_ssh_ports,
    ssh_connect,
)
from ..driver.machine import Machine

# from ..driver.logger import rootlog


KADEPOY_ARCH = {
    "x86_64-linux": "x86_64",
    "powerpc64le-linux": "ppc64le",
    "aarch64-linux": "aarch64",
}

KADEPOY_ENV_DESC = """
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


def generate_kadeploy_envfile(ctx, deploy=None, kernel_params=""):
    if not ctx.compose_info:
        read_compose_info(ctx)

    base_path = op.join(
        ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
    )
    os.makedirs(base_path, mode=0o700, exist_ok=True)
    kaenv_path = op.join(base_path, "nixos.yaml")

    if not deploy:
        if ctx.use_httpd:
            base_url = f"http://{ctx.httpd.ip}:{ctx.httpd.port}"
            deploy = f"{base_url}/deploy/{ctx.composition_flavour_prefix}.json"
        else:
            generate_deploy_info_b64(ctx)
            deploy = ctx.deployment_info_b64

    user = os.environ["USER"]
    system = ctx.compositions_info["system"]
    additional_kernel_params = ""
    if ctx.kernel_params:
        additional_kernel_params = ctx.kernel_params
    with open(kaenv_path, "w") as kaenv_file:
        t = Template(KADEPOY_ENV_DESC)
        kaenv = t.substitute(
            image_name="NixOS",
            author=user,
            system=KADEPOY_ARCH[system],
            file_image_url=f"http://public.grenoble.grid5000.fr/~{user}/nixos.tar.xz",
            kernel_params=f"boot.shell_on_fail console=tty0 console=ttyS0,115200 deploy={deploy} {additional_kernel_params} {ctx.kernel_params}",
        )
        kaenv_file.write(kaenv)


class G5kKexecBasedFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def generate_kexec_scripts(self):
        generate_kexec_scripts(self.ctx)

    def launch(self):
        launch_ssh_kexec(self.ctx)
        time.sleep(10)
        wait_ssh_ports(self.ctx)

    def driver_initialize(self, tmp_dir):
        self.tmp_dir = tmp_dir
        ctx = self.ctx

        if ctx.no_start:  #
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
            exit(1)
        else:
            machine.start_process_shell(
                [
                    "ssh",
                    "-t",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-l",
                    "root",
                    machine.ip,
                ]
            )

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)


class G5kNfsStoreFlavour(G5kKexecBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "g5k-nfs-store"

    def generate_kexec_scripts(self):
        def store_path():
            for prefix_store_path in self.ctx.alternative_stores + ["/nix"]:
                store_path = f"{prefix_store_path}/store"
                if op.exists(store_path):
                    return store_path
            raise "Store Path Not Found"

        if "NFS_STORE" in os.environ:
            kernel_params = f"nfs_store={os.environ['NFS_STORE']}"
        else:
            nfs = socket.getfqdn("nfs")
            store_path = store_path()
            kernel_params = f"nfs_store={nfs}:/export{store_path}"
        self.ctx.vlog(f" kernel_params: {kernel_params}")

        generate_kexec_scripts(self.ctx, flavour_kernel_params=kernel_params)


class G5kRamdiskFlavour(G5kKexecBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "g5k-ramdisk"


class G5KImageFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "g5k-image"

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def launch(self, machine_file=None):
        generate_kadeploy_envfile(self.ctx)
        image_path = realpath_from_store(
            self.ctx, self.ctx.deployment_info["all"]["image"]
        )
        cmd_copy_image = f'cp {image_path} ~{os.environ["USER"]}/public/nixos.tar.xz && chmod 644 ~{os.environ["USER"]}/public/nixos.tar.xz'
        if machine_file or click.confirm(
            f'Do you want to copy image to ~{os.environ["USER"]}/public/nixos.tar.xz ?'
        ):
            try:
                subprocess.call(cmd_copy_image, shell=True)
            except Exception as ex:
                raise click.ClickException(f"Failed to copy image: {ex}")
        else:
            print(f"You can copy image with: {cmd_copy_image}")
        base_path = op.join(
            self.ctx.envdir,
            f"artifact/{self.ctx.composition_name}/{self.ctx.flavour.name}",
        )
        if machine_file:
            cmd_kadeploy = (
                f'kadeploy3 -a {op.join(base_path, "nixos.yaml")} -f {machine_file}'
            )
        else:
            cmd_kadeploy = (
                f'kadeploy3 -a {op.join(base_path, "nixos.yaml")} -f $OAR_NODEFILE'
            )

        if machine_file or click.confirm(
            "Do you want to kadeploy nixos.tar.xz image on nodes from $OAR_NODEFILE"
        ):
            try:
                subprocess.call(cmd_kadeploy, shell=True)
            except Exception as ex:
                raise click.ClickException(f"Failed to execute kadeploy command: {ex}")
        else:
            print(f"You can kadeploy image with: {cmd_kadeploy}")

    def start(self, machine):
        if not self.ctx.no_start:
            print("Not Yet Implemented")
            exit(1)
        else:
            machine.start_process_shell(
                [
                    "ssh",
                    "-t",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-l",
                    "root",
                    machine.ip,
                ]
            )

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)
