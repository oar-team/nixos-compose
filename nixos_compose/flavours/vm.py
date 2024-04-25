import os
import socket
import threading
from queue import Queue
import re
import subprocess
import sys
import shutil
import tempfile
import time

from ..flavour import Flavour
from ..actions import (
    generate_deployment_info,
    ssh_connect,
    kill_proc_tree,
    realpath_from_store,
)
from ..driver.vlan import VLan
from ..driver.logger import rootlog
from ..driver.machine import Machine, make_command, StartCommand
from ..driver.driver import Driver
from ..platform import platform_detection

from pathlib import Path
from typing import List

CHAR_TO_KEY = {
    "A": "shift-a",
    "N": "shift-n",
    "-": "0x0C",
    "_": "shift-0x0C",
    "B": "shift-b",
    "O": "shift-o",
    "=": "0x0D",
    "+": "shift-0x0D",
    "C": "shift-c",
    "P": "shift-p",
    "[": "0x1A",
    "{": "shift-0x1A",
    "D": "shift-d",
    "Q": "shift-q",
    "]": "0x1B",
    "}": "shift-0x1B",
    "E": "shift-e",
    "R": "shift-r",
    ";": "0x27",
    ":": "shift-0x27",
    "F": "shift-f",
    "S": "shift-s",
    "'": "0x28",
    '"': "shift-0x28",
    "G": "shift-g",
    "T": "shift-t",
    "`": "0x29",
    "~": "shift-0x29",
    "H": "shift-h",
    "U": "shift-u",
    "\\": "0x2B",
    "|": "shift-0x2B",
    "I": "shift-i",
    "V": "shift-v",
    ",": "0x33",
    "<": "shift-0x33",
    "J": "shift-j",
    "W": "shift-w",
    ".": "0x34",
    ">": "shift-0x34",
    "K": "shift-k",
    "X": "shift-x",
    "/": "0x35",
    "?": "shift-0x35",
    "L": "shift-l",
    "Y": "shift-y",
    " ": "spc",
    "M": "shift-m",
    "Z": "shift-z",
    "\n": "ret",
    "!": "shift-0x02",
    "@": "shift-0x03",
    "#": "shift-0x04",
    "$": "shift-0x05",
    "%": "shift-0x06",
    "^": "shift-0x07",
    "&": "shift-0x08",
    "*": "shift-0x09",
    "(": "shift-0x0A",
    ")": "shift-0x0B",
}


class VmStartCommand(StartCommand):  # TOMOVE to vm.py
    """The Base Start Command knows how to append the necesary
    runtime qemu options as determined by a particular test driver
    run. Any such start command is expected to happily receive and
    append additional qemu args.
    """

    _cmd: str = ""
    qemu_opts: str = ""

    def __init__(self):
        pass

    def cmd(
        self,
        monitor_socket_path: Path,
        allow_reboot: bool = False,
    ) -> str:
        display_opts = ""
        display_available = any(x in os.environ for x in ["DISPLAY", "WAYLAND_DISPLAY"])
        if not display_available:
            display_opts += " -nographic"

        # qemu options
        qemu_opts = ""
        qemu_opts += (
            ""
            if allow_reboot
            else " -no-reboot" " -device virtio-serial"
            # " -device virtconsole,chardev=shell"
            " -device virtio-rng-pci"
            " -serial stdio"
            f" -monitor unix:{monitor_socket_path}"
        )
        # TODO: qemu script already catpures this env variable, legacy?
        qemu_opts += " " + os.environ.get("QEMU_OPTS", "")

        self.qemu_opts = qemu_opts

        return f"{self._cmd}"

    def build_environment(
        self,
        state_dir: Path,
        shared_dir: Path,
    ) -> dict:
        # We make a copy to not update the current environment
        kernel_params = ""
        if self.driver.ctx.kernel_params:
            kernel_params = self.driver.ctx.kernel_params
        env = dict(os.environ)
        env.update(
            {
                "TMPDIR": str(state_dir),
                "SHARED_DIR": str(shared_dir),
                "USE_TMPDIR": "1",
                "QEMU_OPTS": self.qemu_opts,
                "VM_ID": str(self.vm_id),
                "QEMU_VDE_SOCKET": str(self.driver.vlan.socket_dir),
                "FLAVOUR": f"flavour={self.driver.ctx.flavour.name}",
                "SHARED_NXC_COMPOSITION_DIR": self.driver.ctx.envdir,
                "ADDITIONAL_KERNEL_PARAMS": str(kernel_params),
            }
        )
        return env

    def run(
        self,
        state_dir: Path,
        shared_dir: Path,
        monitor_socket_path: Path,
    ) -> subprocess.Popen:
        return subprocess.Popen(
            self.cmd(monitor_socket_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=state_dir,
            env=self.build_environment(state_dir, shared_dir),
        )


class StartScript(VmStartCommand):
    def __init__(self, script: str, vm_id: str, driver):
        super().__init__()
        self._cmd = script
        self.vm_id = vm_id
        self.driver = driver


class NixStartScript(VmStartCommand):
    """A start script from nixos/modules/virtualiation/qemu-vm.nix
    that also satisfies the requirement of the BaseStartCommand.
    These Nix commands have the particular charactersitic that the
    machine name can be extracted out of them via a regex match.
    (Admittedly a _very_ implicit contract, evtl. TODO fix)
    """

    def __init__(self, script: str, vm_id: str):
        self._cmd = script

    @property
    def machine_name(self) -> str:
        match = re.search("run-(.+)-vm$", self._cmd)
        name = "machine"
        if match:
            name = match.group(1)
        return name


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
        self.shell.terminate()
        self.monitor.close()
        self.serial_thread.join()

    #
    # Below VM specific (upto now) methods
    #
    def log_serial(self, msg: str) -> None:
        rootlog.log_serial(msg, self.name)

    def wait_for_monitor_prompt(self) -> str:
        with self.nested("waiting for monitor prompt"):
            assert self.monitor is not None
            answer = ""
            while True:
                undecoded_answer = self.monitor.recv(1024)
                if not undecoded_answer:
                    break
                answer += undecoded_answer.decode()
                if answer.endswith("(qemu) "):
                    break
            return answer

    def send_monitor_command(self, command: str) -> str:
        with self.nested("sending monitor command: {}".format(command)):
            message = ("{}\n".format(command)).encode()
            assert self.monitor is not None
            self.monitor.send(message)
            return self.wait_for_monitor_prompt()

    def wait_for_shutdown(self) -> None:
        if not self.booted:
            return

        with self.nested("waiting for the VM to power off"):
            sys.stdout.flush()
            assert self.process
            self.process.wait()

            self.pid = None
            self.booted = False
            self.connected = False

    def copy_from_host(self, source: str, target: str) -> None:
        """Copy a file from the host into the guest via the `shared_dir` shared
        among all the VMs (using a temporary directory).
        """
        host_src = Path(source)
        vm_target = Path(target)
        with tempfile.TemporaryDirectory(dir=self.shared_dir) as shared_td:
            shared_temp = Path(shared_td)
            host_intermediate = shared_temp / host_src.name
            vm_shared_temp = Path("/tmp/shared") / shared_temp.name
            vm_intermediate = vm_shared_temp / host_src.name

            self.succeed(make_command(["mkdir", "-p", vm_shared_temp]))
            if host_src.is_dir():
                shutil.copytree(host_src, host_intermediate)
            else:
                shutil.copy(host_src, host_intermediate)
            self.succeed(make_command(["mkdir", "-p", vm_target.parent]))
            self.succeed(make_command(["cp", "-r", vm_intermediate, vm_target]))

    def copy_from_vm(self, source: str, target_dir: str = "") -> None:
        """Copy a file from the VM (specified by an in-VM source path) to a path
        relative to `$out`. The file is copied via the `shared_dir` shared among
        all the VMs (using a temporary directory).
        """
        # Compute the source, target, and intermediate shared file names
        out_dir = Path(os.environ.get("out", os.getcwd()))
        vm_src = Path(source)
        with tempfile.TemporaryDirectory(dir=self.shared_dir) as shared_td:
            shared_temp = Path(shared_td)
            vm_shared_temp = Path("/tmp/shared") / shared_temp.name
            vm_intermediate = vm_shared_temp / vm_src.name
            intermediate = shared_temp / vm_src.name
            # Copy the file to the shared directory inside VM
            self.succeed(make_command(["mkdir", "-p", vm_shared_temp]))
            self.succeed(make_command(["cp", "-r", vm_src, vm_intermediate]))
            abs_target = out_dir / target_dir / vm_src.name
            abs_target.parent.mkdir(exist_ok=True, parents=True)
            # Copy the file from the shared directory outside VM
            if intermediate.is_dir():
                shutil.copytree(intermediate, abs_target)
            else:
                shutil.copy(intermediate, abs_target)

    def send_key(self, key: str) -> None:
        key = CHAR_TO_KEY.get(key, key)
        self.send_monitor_command("sendkey {}".format(key))
        time.sleep(0.01)

    def cleanup_statedir(self) -> None:
        shutil.rmtree(self.state_dir)
        rootlog.log(f"deleting VM state directory {self.state_dir}")
        rootlog.log("if you want to keep the VM state, pass --keep-vm-state")

    def crash(self) -> None:
        if not self.booted:
            return

        self.log("forced crash")
        self.send_monitor_command("quit")
        self.wait_for_shutdown()

    def forward_port(self, host_port: int = 8080, guest_port: int = 80) -> None:
        """Forward a TCP port on the host to a TCP port on the guest.
        Useful during interactive testing.
        """
        self.send_monitor_command(
            "hostfwd_add tcp::{}-:{}".format(host_port, guest_port)
        )

    def block(self) -> None:
        """Make the machine unreachable by shutting down eth1 (the multicast
        interface used to talk to the other VMs).  We keep eth0 up so that
        the test driver can continue to talk to the machine.
        """
        self.send_monitor_command("set_link virtio-net-pci.1 off")

    def unblock(self) -> None:
        """Make the machine reachable."""
        self.send_monitor_command("set_link virtio-net-pci.1 on")


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
