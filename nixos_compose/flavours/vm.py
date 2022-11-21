import os

# import sys
# import json
# import base64
# from ..httpd import HTTPDaemon

from ..flavour import Flavour
from ..actions import (
    generate_deployment_info,
    ssh_connect,
    kill_proc_tree,
    realpath_from_store,
)
from ..driver.vlan import VLan
from ..driver.logger import rootlog
from ..driver.machine import Machine, StartScript
from ..platform import platform_detection


class VmBasedFlavour(Flavour):

    """
    The Vm Ramdisk flavour. This is flavour provides a system image to be executed with QEMU and use memory only for root system. By consequence lot of ram is used around 2Go minimum by node.
    """

    vm = True
    tmp_dir = None
    vlan = None

    def __init__(self, ctx):
        super().__init__(ctx)
        ctx.external_connect = True  # to force use of ssh on foo.execute(command)
        platform_detection(ctx)

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def create_machines(self):
        ctx = self.ctx
        deployment_nodes = ctx.deployment_info["deployment"]
        qemu_script = realpath_from_store(
            ctx, ctx.deployment_info["all"]["qemu_script"]
        )

        for node in deployment_nodes.values():
            start_command = ""
            if not ctx.no_start:
                start_command = StartScript(qemu_script, node["vm_id"], self)
            self.machines.append(
                Machine(
                    ctx,
                    ip="127.0.0.1",
                    ssh_port=f"{22021 + int(node['vm_id'])}",
                    tmp_dir=self.tmp_dir,
                    start_command=start_command,
                    keep_vm_state=False,
                    name=node["host"],
                )
            )

    def driver_initialize(self, tmp_dir):
        self.tmp_dir = tmp_dir
        ctx = self.ctx
        # deployment = ctx.deployment_info

        if ctx.no_start:
            self.create_machines()
            # deployment_nodes = ctx.deployment_info["deployment"]
            # for ip, node in deployment_nodes.items():
            #     ssh_port = 22
            #     if "ssh-port" in node:
            #         ssh_port = node["ssh-port"]
            #     self.machines.append(
            #         Machine(
            #             ctx,
            #             ip=ip,
            #             ssh_port = ssh_port,
            #             tmp_dir=tmp_dir,
            #             start_command="",(qemu_script, v["vm_id"], self)
            #             keep_vm_state=False,
            #             name=node["host"],
            #         )
            #     )

            for machine in self.machines:
                if not machine.connected:
                    self.start(machine)
                machine.connected = True
            return

        # os.environ["KERNEL"] = ctx.deployment["all"]["kernel"]
        # os.environ["INITRD"] = ctx.deployment["all"]["initrd"]
        # base_qemu_script = ctx.deployment["all"]["qemu_script"]

        # debug_stage1 = None
        # debug_var_base = ""
        # if "DEBUG_STAGE1" in os.environ:
        #     debug_stage1 = os.environ["DEBUG_STAGE1"]

        #########
        # Determine DEPLOY data
        #########
        # if "DEPLOY" not in os.environ:
        #     if ctx.use_httpd:
        #         if not ctx.httpd:
        #             ctx.httpd = HTTPDaemon(ctx=ctx)
        #             ctx.httpd.start(directory=ctx.envdir)
        #         base_url = f"http://{ctx.httpd.ip}:{ctx.httpd.port}"
        #         deploy_info_src = (
        #             f"{base_url}/deploy/{ctx.composition_flavour_prefix}.json"
        #         )
        #     else:
        #         if not ctx.deployment_info_b64:
        #             deployment_info_str = json.dumps(deployment)
        #             deploy_info_src = base64.b64encode(
        #                 deployment_info_str.encode()
        #             ).decode()
        #         else:
        #             deploy_info_src = ctx.deployment_info_b64

        #         if len(deploy_info_src) > (4096 - 256):  # 4096 -> 2048 ???
        #             rootlog.nested(
        #                 "The base64 encoded deploy data is too large: use an http server to serve it"
        #             )
        #             sys.exit(1)
        #     os.environ["DEPLOY"] = f"deploy={deploy_info_src}"
        #     print(f"deploy={deploy_info_src}")
        # else:
        #     rootlog.nested(f'Variable environment DEPLOY: {os.environ["DEPLOY"]}')
        if ctx.platform and ctx.platform.nix_store:
            os.environ["SHARED_NIX_STORE_DIR"] = ctx.platform.nix_store
            os.environ["KERNEL"] = realpath_from_store(
                ctx, ctx.deployment_info["all"]["kernel"]
            )
            os.environ["INITRD"] = realpath_from_store(
                ctx, ctx.deployment_info["all"]["initrd"]
            )
            ctx.vlog(f"KERNEL: {os.environ['KERNEL']}")
            ctx.vlog(f"INITRD: {os.environ['INITRD']}")

        if "DEPLOY" not in os.environ:
            os.environ[
                "DEPLOY"
            ] = f"deploy={self.ctx.deployment_filename[len(self.ctx.envdir)+1:]}"
        else:
            rootlog.nested(f'Variable environment DEPLOY: {os.environ["DEPLOY"]}')

        self.create_machines()

    def vlan(self):
        self.vlan = VLan(0, self.tmp_dir, ctx=self.ctx)
        return self.vlan

    def start_process_shell(self, machine):
        machine.start_process_shell(
            [
                "ssh",
                "-t",
                "-o",
                "StrictHostKeyChecking=no",
                "-l",
                "root",
                "-p",
                machine.ssh_port,
                machine.ip,
            ]
        )

    def start(self, machine):
        if not self.ctx.no_start:
            machine._start_vm()
        else:
            self.start_process_shell(machine)

    def release(self, machine):
        if machine.pid is None:
            return
        rootlog.info(f"kill machine (pid {machine.pid})")
        assert machine.process
        assert machine.shell
        assert machine.monitor
        assert machine.serial_thread

        # Kill children
        kill_proc_tree(machine.pid, include_parent=False)

        machine.process.terminate()
        machine.shell.close()
        machine.monitor.close()
        machine.serial_thread.join()

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)


class VmFlavour(VmBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "vm"
        self.image = {"distribution": "all-in-one"}
        self.description = "VM with shared nix-store and stage-1"


class VmRamdiskFlavour(VmBasedFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "vm-ramdisk"
        self.image = {"type": "ramdisk", "distribution": "all-in-one"}
        self.description = "Plain vm ramdisk (all-in-memory), need lot of ram !"
