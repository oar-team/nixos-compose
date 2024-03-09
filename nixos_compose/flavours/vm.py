import os
import socket
import threading
from queue import Queue
import subprocess
import sys

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
from ..driver.driver import Driver
from ..platform import platform_detection

from pathlib import Path
from typing import List


class VmMachine(Machine):
    def __init__(
        self,
        ctx,
        tmp_dir,
        start_command,
        name: str = "machine",
        ip: str = "",
        ssh_port: int = 22,
        keep_vm_state: bool = False,
        allow_reboot: bool = False,
        vm_id: str = "",
        init: str = "",
    ) -> None:
        super().__init__(
            ctx,
            tmp_dir,
            start_command,
            name,
            ip,
            ssh_port,
            keep_vm_state,
            allow_reboot,
            vm_id,
            init,
        )

    def start(self):
        if not self.ctx.no_start:
            if self.booted:
                return

            self.log("starting vm")

            def clear(path: Path) -> Path:
                if path.exists():
                    path.unlink()
                return path

            def create_socket(path: Path) -> socket.socket:
                s = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.bind(str(path))
                s.listen(1)
                return s

            monitor_socket = create_socket(clear(self.monitor_path))
            self.process = self.start_command.run(
                self.state_dir,
                self.shared_dir,
                self.monitor_path,
            )

            try:
                self.monitor, _ = monitor_socket.accept()
            except socket.timeout:
                self.ctx.elog("Time out reached on monitor socket accept (qemu)")
                if self.process.poll():
                    self.ctx.elog(
                        f"Qemu script exited with return code: {self.process.returncode}"
                    )
                    for line in self.process.stdout:
                        self.ctx.elog(f"stdout: {line.decode()}")
                    for line in self.process.stderr:
                        self.ctx.elog(f"stderr: {line.decode()}")
                    sys.exit(1)
                else:
                    self.ctx.elog(f"Qemu seems stucks, pid: {self.process.pid}")
                    sys.exit(1)

            # Store last serial console lines for use
            # of wait_for_console_text
            self.last_lines: Queue = Queue()

            def process_serial_output() -> None:
                assert self.process
                assert self.process.stdout
                for _line in self.process.stdout:
                    # Ignore undecodable bytes that may occur in boot menus
                    line = _line.decode(errors="ignore").replace("\r", "").rstrip()
                    self.last_lines.put(line)
                    self.log_serial(line)

            self.serial_thread = threading.Thread(target=process_serial_output)
            # self.serial_thread.daemon = True
            self.serial_thread.start()

            self.wait_for_monitor_prompt()

            # For now we use ssh for shell access (see: start in flavours/vm.py)
            # nixos-test use a backdoor see nixpkgs/nixos/modules/testing/test-instrumentation.nix
            ssh_cmd = VmFlavour.driver.default_connect("root", self.name, False)
            self.shell = subprocess.Popen(
                ssh_cmd,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # self.shell = subprocess.Popen(
            #     [
            #         "ssh",
            #         "-t",
            #         "-o",
            #         "StrictHostKeyChecking=no",
            #         "-l",
            #         "root",
            #         "-p",
            #         self.ssh_port,
            #         self.ip,
            #     ],
            #     stdin=subprocess.PIPE,
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.PIPE,
            # )

            self.pid = self.process.pid
            self.booted = True

            self.log("QEMU running (pid {})".format(self.pid))

        # For now we use ssh for shell access (see: start in flavours/vm.py)
        # nixos-test use a backdoor see nixpkgs/nixos/modules/testing/test-instrumentation.nix

        # self.shell = subprocess.Popen(
        #     [
        #         "ssh",
        #         "-t",
        #         "-o",
        #         "StrictHostKeyChecking=no",
        #         "-l",
        #         "root",
        #         "-p",
        #         self.ssh_port,
        #         self.ip,
        #     ],
        #     stdin=subprocess.PIPE,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        # )
        ssh_cmd = VmFlavour.driver.default_connect("root", self.name, False)
        self.shell = subprocess.Popen(
            ssh_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def shell_interact(self) -> None:
        self.connect()
        VmFlavour.driver.default_connect("root", self.name)

    def release(self):
        if self.pid is None:
            return
        rootlog.info(f"kill {self.name} VM (pid {self.pid})")
        assert self.process
        assert self.monitor
        assert self.serial_thread

        # Kill children
        kill_proc_tree(self.pid, include_parent=False)

        self.process.terminate()
        self.monitor.close()
        self.serial_thread.join()


class VmDriver(Driver):
    vlan = None
    tmp_dir: str

    def __init__(self, ctx, start_scripts, tests, keep_vm_state):
        self.tmp_dir = super().__init__(ctx, start_scripts, tests, keep_vm_state)

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

            # TO REMOVE
            # for machine in self.machines:
            #     if not machine.connected:
            #         machine.start()
            #     machine.connected = True
        else:
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

            # Create VLAN
            self.vlan = VLan(0, self.tmp_dir, ctx=self.ctx)

            self.create_machines()

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
                VmMachine(
                    ctx,
                    ip="127.0.0.1",
                    ssh_port=f"{22021 + int(node['vm_id'])}",
                    tmp_dir=self.tmp_dir,
                    start_command=start_command,
                    keep_vm_state=False,
                    name=node["host"],
                )
            )

    def default_connect(self, user, machine, execute=True, ssh_key_file=None):
        return ssh_connect(self.ctx, user, machine, execute, ssh_key_file)


class VmBaseFlavour(Flavour):
    """
    The Vm Ramdisk flavour. This is flavour provides a system image to be executed with QEMU and use memory only for root system. By consequence lot of ram is used around 2Go minimum by node.
    """

    driver = None
    vm = True  # TOREMOVE ???

    def __init__(self, ctx):
        super().__init__(ctx)
        ctx.external_connect = True  # to force use of ssh on foo.execute(command)
        platform_detection(ctx)

    def generate_deployment_info(self, ssh_pub_key_file=None):
        generate_deployment_info(self.ctx, ssh_pub_key_file)

    def initialize_driver(
        self,
        ctx,
        start_scripts: List[str] = [],
        tests: str = "",
        keep_vm_state: bool = False,
    ):
        VmBaseFlavour.driver = VmDriver(ctx, start_scripts, tests, keep_vm_state)
        return VmBaseFlavour.driver

    # def create_vlan(self):
    #     self.vlan = VLan(0, self.tmp_dir, ctx=self.ctx)
    #     return self.vlan

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

    # TOREMOVE
    # def start(self, machine):

    #     if not self.ctx.no_start:
    #         machine._start_vm()
    #     else:
    #         self.start_process_shell(machine)

    # def release(self, machine):
    #     if machine.pid is None:
    #         return
    #     rootlog.info(f"kill machine (pid {machine.pid})")
    #     assert machine.process
    #     assert machine.shell
    #     assert machine.monitor
    #     assert machine.serial_thread

    #     # Kill children
    #     kill_proc_tree(machine.pid, include_parent=False)

    #     machine.process.terminate()
    #     machine.shell.close()
    #     machine.monitor.close()
    #     machine.serial_thread.join()

    def ext_connect(self, user, node, execute=True, ssh_key_file=None):
        return ssh_connect(self.ctx, user, node, execute, ssh_key_file)


class VmFlavour(VmBaseFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "vm"
        self.image = {"distribution": "all-in-one"}
        self.description = "VM with shared nix-store and stage-1"


class VmRamdiskFlavour(VmBaseFlavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "vm-ramdisk"
        self.image = {"type": "ramdisk", "distribution": "all-in-one"}
        self.description = "Plain vm ramdisk (all-in-memory), need lot of ram !"
