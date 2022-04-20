import os
import sys
import json
import base64
import subprocess
from ..httpd import HTTPDaemon

from ..flavour import Flavour
from ..actions import generate_deployment_info, ssh_connect, kill_proc_tree
from ..driver.vlan import VLan
from ..driver.logger import rootlog
from ..driver.machine import Machine, StartScript


class VmRamdiskFlavour(Flavour):
    """
    The Vm Ramdisk flavour. This is flavour provides a system image to be executed with QEMU and use memory only for root system. By consequence lot of ram is used around 2Go minimum by node.
    """

    vm = True
    tmp_dir = None
    vlan = None

    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "vm-ramdisk"
        self.image = {"type": "ramdisk", "distribution": "all-in-one"}
        self.description = "Plain vm ramdisk (all-in-memory), need lot of ram !"

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def driver_initialize(self, tmp_dir):
        self.tmp_dir = tmp_dir

        ctx = self.ctx
        deployment = ctx.deployment_info

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

        os.environ["KERNEL"] = deployment["all"]["kernel"]
        os.environ["INITRD"] = deployment["all"]["initrd"]
        base_qemu_script = deployment["all"]["qemu_script"]

        debug_stage1 = None
        debug_var_base = ""
        if "DEBUG_STAGE1" in os.environ:
            debug_stage1 = os.environ["DEBUG_STAGE1"]

        if "DEPLOY" not in os.environ:
            if ctx.use_httpd:
                if not ctx.httpd:
                    ctx.httpd = HTTPDaemon(ctx=ctx)
                    ctx.httpd.start(directory=ctx.envdir)
                base_url = f"http://10.0.2.2:{ctx.httpd.port}"
                deploy_info_src = (
                    f"{base_url}/deploy/{ctx.composition_flavour_prefix}.json"
                )
            else:
                if not ctx.deployment_info_b64:
                    deployment_info_str = json.dumps(deployment)
                    deploy_info_src = base64.b64encode(
                        deployment_info_str.encode()
                    ).decode()
                else:
                    deploy_info_src = ctx.deployment_info_b64
                if len(deploy_info_src) > (4096 - 256):
                    rootlog.nested(
                        "The base64 encoded deploy data is too large: use an http server to serve it"
                    )
                    sys.exit(1)
            os.environ["DEPLOY"] = f"deploy={deploy_info_src}"
            print(f"deploy={deploy_info_src}")
        else:
            rootlog.nested(f'Variable environment DEPLOY: {os.environ["DEPLOY"]}')

        for var_env in ["QEMU_APPEND", "DEBUG_INITRD"]:
            if var_env in os.environ:
                rootlog.nested(f"Variable environment {var_env}: {os.environ[var_env]}")

        if debug_stage1:
            debug_var_base = f'KERNEL={deployment["all"]["kernel"]} \\\nINITRD={deployment["all"]["initrd"]} \\\n'
        base_qemu_script = deployment["all"]["qemu_script"]

        ip_addresses = []
        for i in range(len(deployment["deployment"])):
            ip = "10.0.2.{}".format(15 + i)
            ip_addresses.append(ip)
            if ip not in deployment["deployment"]:
                rootlog.nested(f"In vm mode, {ip} must be present")
                sys.exit(1)
            v = deployment["deployment"][ip]

            name = v["host"]

            if base_qemu_script:
                qemu_script = base_qemu_script
            else:
                qemu_script = v["qemu_script"]

            if debug_stage1:
                if debug_stage1 == name:
                    # debloy="DEPLOY=deploy=http://10.0.2.1:8000/deploy/composition::vm-ramdisk.json \\\n"
                    # deploy="DEPLOY=deploy={ctx.deploy_info_src}"
                    params = f'{debug_var_base}INIT={v["init"]} \\\n'
                    debug = " DEBUG_INITRD=boot.debug1mounts "
                    # params = f'{params}QEMU_VDE_SOCKET={self.vlan.socket_dir}{debug}VM_ID={v["vm_id"]} ROLE={name}\\\n'
                    params = f'{params}QEMU_VDE_SOCKET={self.vlan.socket_dir}{debug}VM_ID={v["vm_id"]} \\\n'
                    if "DEPLOY" in os.environ:
                        params = f'DEPLOY={os.environ["DEPLOY"]} \\\n{params}'
                    print()
                    print(f"DEBUG STAGE1 on role: {name}")
                    print(f"{params}{qemu_script}")
                    # subprocess.call(f"{params} bash -x {qemu_script}", shell=True)
                    subprocess.call(f"{params}{qemu_script}", shell=True)
                    sys.exit(0)
            else:

                self.machines.append(
                    Machine(
                        self.ctx,
                        tmp_dir=tmp_dir,
                        start_command=StartScript(qemu_script, v["vm_id"], self),
                        name=name,
                        ip=ip,
                        keep_vm_state=False,
                        vm_id=v["vm_id"],
                        init=v["init"],
                    )
                )

    def vlan(self):
        self.vlan = VLan(0, self.tmp_dir, tap0=True)
        return self.vlan

    def start(self, machine):
        if not self.ctx.no_start:
            machine._start_vm()
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

    # def start_all(self):
    #    with rootlog.nested("start all VMs"):

    # def start_composition(self):
    #     pass

    # def driver_start(self):
    #     pass
