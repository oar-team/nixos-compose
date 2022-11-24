from contextlib import _GeneratorContextManager
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple
import base64
import io
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

from .logger import rootlog
from ..flavours import use_flavour_method_if_any

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


def make_command(args: list) -> str:
    return " ".join(map(shlex.quote, (map(str, args))))


def retry(fn: Callable, timeout: int = 900) -> None:
    """Call the given function repeatedly, with 1 second intervals,
    until it returns True or a timeout is reached.
    """

    for _ in range(timeout):
        if fn(False):
            return
        time.sleep(1)

    if not fn(True):
        raise Exception(f"action timed out after {timeout} seconds")


class StartCommand:
    pass


class VmStartCommand(StartCommand):
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
        shell_socket_path: Path,
        allow_reboot: bool = False,  # TODO: unused, legacy?
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
            else " -no-reboot"
            " -device virtio-serial"
            " -device virtconsole,chardev=shell"
            " -device virtio-rng-pci"
            " -serial stdio"
            f" -monitor unix:{monitor_socket_path}"
            f" -chardev socket,id=shell,path={shell_socket_path}"
        )
        # TODO: qemu script already catpures this env variable, legacy?
        qemu_opts += " " + os.environ.get("QEMU_OPTS", "")

        self.qemu_opts = qemu_opts

        return f"{self._cmd}"

    def build_environment(self, state_dir: Path, shared_dir: Path,) -> dict:
        # We make a copy to not update the current environment
        kernel_params = ""
        if self.flavour.ctx.kernel_params:
            kernel_params = self.flavour.ctx.kernel_params
        env = dict(os.environ)
        env.update(
            {
                "TMPDIR": str(state_dir),
                "SHARED_DIR": str(shared_dir),
                "USE_TMPDIR": "1",
                "QEMU_OPTS": self.qemu_opts,
                "VM_ID": str(self.vm_id),
                "QEMU_VDE_SOCKET": str(self.flavour.vlan.socket_dir),
                "FLAVOUR": f"flavour={self.flavour.name}",
                "SHARED_NXC_COMPOSITION_DIR": self.flavour.ctx.envdir,
                "ADDITIONAL_KERNEL_PARAMS": str(kernel_params),
            }
        )
        return env

    def run(
        self,
        state_dir: Path,
        shared_dir: Path,
        monitor_socket_path: Path,
        shell_socket_path: Path,
    ) -> subprocess.Popen:
        return subprocess.Popen(
            self.cmd(monitor_socket_path, shell_socket_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=state_dir,
            env=self.build_environment(state_dir, shared_dir),
        )


class StartScript(VmStartCommand):
    def __init__(self, script: str, vm_id: str, flavour):
        super().__init__()
        self._cmd = script
        self.vm_id = vm_id
        self.flavour = flavour


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


class Machine:
    """A handle to the machine with this name, that also knows how to manage
    the machine lifecycle with the help of a start script / command."""

    name: str
    tmp_dir: Path
    shared_dir: Path
    state_dir: Path
    monitor_path: Path
    shell_path: Path

    start_command: StartCommand
    keep_vm_state: bool
    allow_reboot: bool

    process: Optional[subprocess.Popen]
    pid: Optional[int]
    monitor: Optional[socket.socket]
    shell: Optional[socket.socket]
    serial_thread: Optional[threading.Thread]
    process_shell: Optional[subprocess.Popen]

    booted: bool
    connected: bool
    # Store last serial console lines for use
    # of wait_for_console_text
    last_lines: Queue = Queue()
    ctx = None

    def __repr__(self) -> str:
        return f"<Machine '{self.name}'>"

    def __init__(
        self,
        ctx,
        tmp_dir: Path,
        start_command: StartCommand,
        name: str = "machine",
        ip: str = "",
        ssh_port: int = 22,
        keep_vm_state: bool = False,
        allow_reboot: bool = False,
        vm_id: str = "",
        init: str = "",
    ) -> None:
        self.ctx = ctx
        self.tmp_dir = tmp_dir
        self.keep_vm_state = keep_vm_state
        self.allow_reboot = allow_reboot
        self.name = name
        self.start_command = start_command
        self.ip = ip
        self.ssh_port = ssh_port
        self.vm_id = vm_id
        self.init = init

        # set up directories (TODO only for vm ???)
        self.shared_dir = self.tmp_dir / "shared-xchg"
        self.shared_dir.mkdir(mode=0o700, exist_ok=True)

        self.state_dir = self.tmp_dir / f"vm-state-{self.name}"
        self.monitor_path = self.state_dir / "monitor"
        self.shell_path = self.state_dir / "shell"
        if (not self.keep_vm_state) and self.state_dir.exists():
            self.cleanup_statedir()
        self.state_dir.mkdir(mode=0o700, exist_ok=True)

        self.process = None
        self.pid = None
        self.monitor = None
        self.shell = None
        self.serial_thread = None

        self.booted = False
        self.connected = False

    def is_up(self) -> bool:
        return self.booted and self.connected

    def log(self, msg: str) -> None:
        rootlog.log(msg, {"machine": self.name})

    def log_serial(self, msg: str) -> None:
        rootlog.log_serial(msg, self.name)

    def nested(self, msg: str, attrs: Dict[str, str] = {}) -> _GeneratorContextManager:
        my_attrs = {"machine": self.name}
        my_attrs.update(attrs)
        return rootlog.nested(msg, my_attrs)

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

    def wait_for_unit(self, unit: str, user: Optional[str] = None) -> None:
        """Wait for a systemd unit to get into "active" state.
        Throws exceptions on "failed" and "inactive" states as well as
        after timing out.
        """

        def check_active(_: Any) -> bool:
            info = self.get_unit_info(unit, user)
            state = info["ActiveState"]
            if state == "failed":
                raise Exception('unit "{}" reached state "{}"'.format(unit, state))

            if state == "inactive":
                status, jobs = self.systemctl("list-jobs --full 2>&1", user)
                if "No jobs" in jobs:
                    info = self.get_unit_info(unit, user)
                    if info["ActiveState"] == state:
                        raise Exception(
                            (
                                'unit "{}" is inactive and there ' "are no pending jobs"
                            ).format(unit)
                        )

            return state == "active"

        with self.nested(
            "waiting for unit {}{}".format(
                unit, f" with user {user}" if user is not None else ""
            )
        ):
            retry(check_active)

    def get_unit_info(self, unit: str, user: Optional[str] = None) -> Dict[str, str]:
        status, lines = self.systemctl('--no-pager show "{}"'.format(unit), user)
        if status != 0:
            raise Exception(
                'retrieving systemctl info for unit "{}" {} failed with exit code {}'.format(
                    unit, "" if user is None else 'under user "{}"'.format(user), status
                )
            )

        line_pattern = re.compile(r"^([^=]+)=(.*)$")

        def tuple_from_line(line: str) -> Tuple[str, str]:
            match = line_pattern.match(line)
            assert match is not None
            return match[1], match[2]

        return dict(
            tuple_from_line(line)
            for line in lines.split("\n")
            if line_pattern.match(line)
        )

    def systemctl(self, q: str, user: Optional[str] = None) -> Tuple[int, str]:
        if user is not None:
            q = q.replace("'", "\\'")
            return self.execute(
                (
                    "su -l {} --shell /bin/sh -c "
                    "$'XDG_RUNTIME_DIR=/run/user/`id -u` "
                    "systemctl --user {}'"
                ).format(user, q)
            )
        return self.execute("systemctl {}".format(q))

    def require_unit_state(self, unit: str, require_state: str = "active") -> None:
        with self.nested(
            "checking if unit ‘{}’ has reached state '{}'".format(unit, require_state)
        ):
            info = self.get_unit_info(unit)
            state = info["ActiveState"]
            if state != require_state:
                raise Exception(
                    "Expected unit ‘{}’ to to be in state ".format(unit)
                    + "'{}' but it is in state ‘{}’".format(require_state, state)
                )

    def _next_newline_closed_block_from_shell(self) -> str:
        assert self.shell
        output_buffer = []
        while True:
            # This receives up to 4096 bytes from the socket
            chunk = self.shell.recv(4096)
            if not chunk:
                # Probably a broken pipe, return the output we have
                break
            decoded = chunk.decode()
            output_buffer += [decoded]
            if decoded[-1] == "\n":
                break
        return "".join(output_buffer)

    @use_flavour_method_if_any
    def execute(
        self, command: str, check_return: bool = True, timeout: Optional[int] = 900
    ) -> Tuple[int, str]:
        # For now we use ssh for shell access (see: start in flavours/vm.py)
        # nixos-test use a backdoor see nixpkgs/nixos/modules/testing/test-instrumentation.nix
        if self.ctx.external_connect:
            return self.execute_process_shell(command, check_return, timeout)

        self.connect()

        if timeout is not None:
            command = "timeout {} sh -c {}".format(timeout, shlex.quote(command))

        out_command = f"( set -euo pipefail; {command} ) | (base64 --wrap 0; echo)\n"
        assert self.shell
        self.shell.send(out_command.encode())

        # Get the output
        output = base64.b64decode(self._next_newline_closed_block_from_shell())

        if not check_return:
            return (-1, output.decode())

        # Get the return code
        self.shell.send("echo ${PIPESTATUS[0]}\n".encode())
        rc = int(self._next_newline_closed_block_from_shell().strip())

        return (rc, output.decode())

    @use_flavour_method_if_any
    def shell_interact(self) -> None:
        """Allows you to interact with the guest shell
        Should only be used during test development, not in the production test."""

        self.connect()
        self.log("Terminal is ready (there is no prompt):")

        assert self.shell
        subprocess.run(
            ["socat", "READLINE", f"FD:{self.shell.fileno()}"],
            pass_fds=[self.shell.fileno()],
        )

    def succeed(self, *commands: str, timeout: Optional[int] = None) -> str:
        """Execute each command and check that it succeeds."""
        output = ""
        for command in commands:
            with self.nested("must succeed: {}".format(command)):
                (status, out) = self.execute(command, timeout=timeout)
                if status != 0:
                    self.log("output: {}".format(out))
                    raise Exception(
                        "command `{}` failed (exit code {})".format(command, status)
                    )
                output += out
        return output

    def fail(self, *commands: str, timeout: Optional[int] = None) -> str:
        """Execute each command and check that it fails."""
        output = ""
        for command in commands:
            with self.nested("must fail: {}".format(command)):
                (status, out) = self.execute(command, timeout=timeout)
                if status == 0:
                    raise Exception(
                        "command `{}` unexpectedly succeeded".format(command)
                    )
                output += out
        return output

    def wait_until_succeeds(self, command: str, timeout: int = 900) -> str:
        """Wait until a command returns success and return its output.
        Throws an exception on timeout.
        """
        output = ""

        def check_success(_: Any) -> bool:
            nonlocal output
            status, output = self.execute(command, timeout=timeout)
            return status == 0

        with self.nested("waiting for success: {}".format(command)):
            retry(check_success, timeout)
            return output

    def wait_until_fails(self, command: str, timeout: int = 900) -> str:
        """Wait until a command returns failure.
        Throws an exception on timeout.
        """
        output = ""

        def check_failure(_: Any) -> bool:
            nonlocal output
            status, output = self.execute(command, timeout=timeout)
            return status != 0

        with self.nested("waiting for failure: {}".format(command)):
            retry(check_failure)
            return output

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

    def get_tty_text(self, tty: str) -> str:
        status, output = self.execute(
            "fold -w$(stty -F /dev/tty{0} size | "
            "awk '{{print $2}}') /dev/vcs{0}".format(tty)
        )
        return output

    def wait_until_tty_matches(self, tty: str, regexp: str) -> None:
        """Wait until the visible output on the chosen TTY matches regular
        expression. Throws an exception on timeout.
        """
        matcher = re.compile(regexp)

        def tty_matches(last: bool) -> bool:
            text = self.get_tty_text(tty)
            if last:
                self.log(
                    f"Last chance to match /{regexp}/ on TTY{tty}, "
                    f"which currently contains: {text}"
                )
            return len(matcher.findall(text)) > 0

        with self.nested("waiting for {} to appear on tty {}".format(regexp, tty)):
            retry(tty_matches)

    def send_chars(self, chars: List[str]) -> None:
        with self.nested("sending keys ‘{}‘".format(chars)):
            for char in chars:
                self.send_key(char)

    def wait_for_file(self, filename: str) -> None:
        """Waits until the file exists in machine's file system."""

        def check_file(_: Any) -> bool:
            status, _ = self.execute("test -e {}".format(filename))
            return status == 0

        with self.nested("waiting for file ‘{}‘".format(filename)):
            retry(check_file)

    def wait_for_open_port(self, port: int) -> None:
        def port_is_open(_: Any) -> bool:
            status, _ = self.execute("nc -z localhost {}".format(port))
            return status == 0

        with self.nested("waiting for TCP port {}".format(port)):
            retry(port_is_open)

    def wait_for_closed_port(self, port: int) -> None:
        def port_is_closed(_: Any) -> bool:
            status, _ = self.execute("nc -z localhost {}".format(port))
            return status != 0

        with self.nested("waiting for TCP port {} to be closed"):
            retry(port_is_closed)

    def start_job(self, jobname: str, user: Optional[str] = None) -> Tuple[int, str]:
        return self.systemctl("start {}".format(jobname), user)

    def stop_job(self, jobname: str, user: Optional[str] = None) -> Tuple[int, str]:
        return self.systemctl("stop {}".format(jobname), user)

    def wait_for_job(self, jobname: str) -> None:
        self.wait_for_unit(jobname)

    @use_flavour_method_if_any
    def connect(self) -> None:
        if self.connected:
            return

        with self.nested("waiting for the VM to finish booting"):
            self.start()

            assert self.shell

            tic = time.time()
            self.shell.recv(1024)
            # TODO: Timeout
            toc = time.time()

            self.log("connected to guest root shell")
            self.log("(connecting took {:.2f} seconds)".format(toc - tic))
            self.connected = True

    def copy_from_host_via_shell(self, source: str, target: str) -> None:
        """Copy a file from the host into the guest by piping it over the
        shell into the destination file. Works without host-guest shared folder.
        Prefer copy_from_host for whenever possible.
        """
        with open(source, "rb") as fh:
            content_b64 = base64.b64encode(fh.read()).decode()
            self.succeed(
                f"mkdir -p $(dirname {target})",
                f"echo -n {content_b64} | base64 -d > {target}",
            )

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

    def dump_tty_contents(self, tty: str) -> None:
        """Debugging: Dump the contents of the TTY<n>"""
        self.execute("fold -w 80 /dev/vcs{} | systemd-cat".format(tty))

    def wait_for_console_text(self, regex: str) -> None:
        with self.nested("waiting for {} to appear on console".format(regex)):
            # Buffer the console output, this is needed
            # to match multiline regexes.
            console = io.StringIO()
            while True:
                try:
                    console.write(self.last_lines.get())
                except queue.Empty:
                    self.sleep(1)
                    continue
                console.seek(0)
                matches = re.search(regex, console.read())
                if matches is not None:
                    return

    def send_key(self, key: str) -> None:
        key = CHAR_TO_KEY.get(key, key)
        self.send_monitor_command("sendkey {}".format(key))
        time.sleep(0.01)

    def start(self) -> None:
        self.ctx.flavour.start(self)

    def _start_vm(self) -> None:
        """Should work for vm-ramdisk (tested) and other qemu based (not tested)"""
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
        shell_socket = create_socket(clear(self.shell_path))
        self.process = self.start_command.run(
            self.state_dir, self.shared_dir, self.monitor_path, self.shell_path,
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

        # For now we use ssh for shell access (see: start in flavours/vm.py)
        # nixos-test use a backdoor see nixpkgs/nixos/modules/testing/test-instrumentation.nix
        self.shell, _ = shell_socket.accept()
        self.ctx.flavour.start_process_shell(self)

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

        self.pid = self.process.pid
        self.booted = True

        self.log("QEMU running (pid {})".format(self.pid))

    def cleanup_statedir(self) -> None:
        if self.ctx.flavour in ["vm", "vm-ramdisk"]:
            shutil.rmtree(self.state_dir)
            rootlog.log(f"deleting VM state directory {self.state_dir}")
            rootlog.log("if you want to keep the VM state, pass --keep-vm-state")

    def shutdown(self) -> None:
        if not self.booted:
            return

        assert self.shell
        self.shell.send("poweroff\n".encode())
        self.wait_for_shutdown()

    def crash(self) -> None:
        if not self.booted:
            return

        self.log("forced crash")
        self.send_monitor_command("quit")
        self.wait_for_shutdown()

    def wait_for_x(self) -> None:
        """Wait until it is possible to connect to the X server.  Note that
        testing the existence of /tmp/.X11-unix/X0 is insufficient.
        """

        def check_x(_: Any) -> bool:
            cmd = (
                "journalctl -b SYSLOG_IDENTIFIER=systemd | "
                + 'grep "Reached target Current graphical"'
            )
            status, _ = self.execute(cmd)
            if status != 0:
                return False
            status, _ = self.execute("[ -e /tmp/.X11-unix/X0 ]")
            return status == 0

        with self.nested("waiting for the X11 server"):
            retry(check_x)

    def get_window_names(self) -> List[str]:
        return self.succeed(
            r"xwininfo -root -tree | sed 's/.*0x[0-9a-f]* \"\([^\"]*\)\".*/\1/; t; d'"
        ).splitlines()

    def wait_for_window(self, regexp: str) -> None:
        pattern = re.compile(regexp)

        def window_is_visible(last_try: bool) -> bool:
            names = self.get_window_names()
            if last_try:
                self.log(
                    "Last chance to match {} on the window list,".format(regexp)
                    + " which currently contains: "
                    + ", ".join(names)
                )
            return any(pattern.search(name) for name in names)

        with self.nested("waiting for a window to appear"):
            retry(window_is_visible)

    def sleep(self, secs: int) -> None:
        # We want to sleep in *guest* time, not *host* time.
        self.succeed(f"sleep {secs}")

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

    @use_flavour_method_if_any
    def release(self) -> None:

        if self.pid is None:
            return

        rootlog.info(f"kill machine (pid {self.pid})")

        assert self.process
        assert self.shell
        assert self.monitor
        assert self.serial_thread

        self.process.terminate()
        self.shell.close()
        self.monitor.close()
        self.serial_thread.join()

    def start_process_shell(self, args):
        # command examples:
        # ['docker-compose', '-f', '/home/auguste/work/tests/21-22/nxc-test/nxc/deploy/docker_compose/docker-compose.json', 'exec', '-T', ']

        # ['ssh', '-t', '-o', 'StrictHostKeyChecking=no', '-l', 'root', '10.0.2.16']
        self.process_shell = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def execute_process_shell(
        self, command: str, check_return: bool = True, timeout: Optional[int] = 900,
    ) -> Tuple[int, str]:

        self.connect()

        process_shell = self.process_shell

        try:
            (stdout, _stderr) = process_shell.communicate(
                command.encode(), timeout=timeout
            )
        except subprocess.TimeoutExpired:
            process_shell.kill()
            return (-1, "")

        status_code = process_shell.returncode
        self.restart_process_shell()

        if not check_return:
            return (-1, stdout.decode())

        return (status_code, stdout.decode())

    def restart_process_shell(self):
        self.start()
