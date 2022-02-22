import os
import os.path as op
import time
from string import Template
import click
import subprocess

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


def generate_kadeploy_envfile(ctx, deploy=None, kernel_params_opts=""):
    if not ctx.compose_info:
        read_compose_info(ctx)

    base_path = op.join(
        ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
    )
    os.makedirs(base_path, mode=0o700, exist_ok=True)
    kaenv_path = op.join(base_path, "nixos.yaml")
    if not deploy:
        generate_deploy_info_b64(ctx)
        deploy = ctx.deployment_info_b64

    user = os.environ["USER"]
    system = ctx.compositions_info["system"]
    with open(kaenv_path, "w") as kaenv_file:
        t = Template(KADEPOY_ENV_DESC)
        kaenv = t.substitute(
            image_name="NixOS",
            author=user,
            system=KADEPOY_ARCH[system],
            file_image_url=f"http://public.grenoble.grid5000.fr/~{user}/nixos.tar.xz",
            kernel_params=f"boot.shell_on_fail console=tty0 console=ttyS0,115200 deploy={deploy} {kernel_params_opts}",
        )
        kaenv_file.write(kaenv)


class G5kRamdiskFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "g5k-ramdisk"

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def generate_kexec_scripts(self):
        generate_kexec_scripts(self.ctx)

    def launch(self):
        launch_ssh_kexec(self.ctx)
        time.sleep(10)
        wait_ssh_ports(self.ctx)

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)


class G5KImageFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "g5k-image"

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def launch(self):
        generate_kadeploy_envfile(self.ctx)
        image_path = realpath_from_store(
            self.ctx, self.ctx.deployment_info["all"]["image"]
        )
        cmd_copy_image = f'cp {image_path} ~{os.environ["USER"]}/public/nixos.tar.xz && chmod 644 ~{os.environ["USER"]}/public/nixos.tar.xz'
        if click.confirm(
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
        cmd_kadeploy = (
            f'kadeploy3 -a {op.join(base_path, "nixos.yaml")} -f $OAR_NODEFILE -k'
        )

        if click.confirm(
            "Do you want to kadeploy nixos.tar.xz image on nodes from $OAR_NODEFILE"
        ):
            try:
                subprocess.call(cmd_kadeploy, shell=True)
            except Exception as ex:
                raise click.ClickException(f"Failed to execute kadeploy command: {ex}")
        else:
            print(f"You can kadeploy image with: {cmd_kadeploy}")

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)
