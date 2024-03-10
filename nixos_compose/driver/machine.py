from contextlib import _GeneratorContextManager
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple
import base64
import io
import queue
import re
import shlex
import socket
import subprocess
import threading
import time

from .logger import rootlog


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


class Machine:
    """A handle to the machine with this name, that also knows how to manage
    the machine lifecycle with the help of a start script / command."""

    name: str
    tmp_dir: Path
    shared_dir: Path
    state_dir: Path
    monitor_path: Path

    start_command: StartCommand
    keep_vm_state: bool
    allow_reboot: bool

    process: Optional[subprocess.Popen]
    pid: Optional[int]
    monitor: Optional[socket.socket]
    shell: Optional[subprocess.Popen]
    serial_thread: Optional[threading.Thread]

    booted: bool
    connected: bool
    # Store last serial console lines for use
    # of wait_for_console_text
    last_lines: Queue = Queue()
    callbacks: List[Callable]

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
        callbacks: Optional[List[Callable]] = None,
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
        self.callbacks = callbacks if callbacks is not None else []

        # set up directories (TODO only for vm ???)
        self.shared_dir = self.tmp_dir / "shared-xchg"
        self.shared_dir.mkdir(mode=0o700, exist_ok=True)

        self.state_dir = self.tmp_dir / f"vm-state-{self.name}"
        self.monitor_path = self.state_dir / "monitor"
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

    def nested(self, msg: str, attrs: Dict[str, str] = {}) -> _GeneratorContextManager:
        my_attrs = {"machine": self.name}
        my_attrs.update(attrs)
        return rootlog.nested(msg, my_attrs)

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

    def execute(
        self,
        command: str,
        check_return: bool = True,
        timeout: Optional[int] = 900,
    ) -> Tuple[int, str]:
        self.run_callbacks()
        self.connect()

        assert self.shell

        try:
            (stdout, _stderr) = self.shell.communicate(
                command.encode(), timeout=timeout
            )
        except subprocess.TimeoutExpired:
            self.shell.kill()
            return (-1, "")

        status_code = self.shell.returncode

        # If process gone we need to restart one for next command
        # Need more investigation why we cannot reuse previous shell...
        if self.shell.poll() is not None:
            # print("need to restart process")
            self.start()

        if not check_return:
            return (-1, stdout.decode())

        return (status_code, stdout.decode())

    # def shell_interact(self) -> None:
    #     """Allows you to interact with the guest shell
    #     Should only be used during test development, not in the production test."""

    #     self.connect()
    #     self.log("Terminal is ready (there is no prompt):")

    #     assert self.shell
    #     subprocess.run(
    #         ["socat", "READLINE", f"FD:{self.shell.fileno()}"],
    #         pass_fds=[self.shell.fileno()],
    #     )

    def shell_interact(self) -> None:
        raise Exception("Not YET implemented for this flavour")

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
        raise Exception("Not YET implemented for this flavour")

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

    def connect(self) -> None:
        if self.connected:
            return

        self.start()
        assert self.shell
        self.connected = True

        # with self.nested("waiting for the node to finish booting"):
        #     self.start()

        #     assert self.shell

        #     tic = time.time()
        #     self.shell.recv(1024)
        #     # TODO: Timeout
        #     toc = time.time()

        #     self.log("connected to node root shell")
        #     self.log("(connecting took {:.2f} seconds)".format(toc - tic))
        #     self.connected = True

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
        """Copy a file from the host."""
        raise Exception("Not YET implemented for this flavour")

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

    def start(self) -> None:
        raise Exception("Not YET implemented for this flavour")

    def cleanup_statedir(self) -> None:
        raise Exception("Not YET implemented for this flavour")

    def shutdown(self) -> None:
        if not self.booted:
            return

        assert self.shell
        self.shell.send("poweroff\n".encode())
        self.wait_for_shutdown()

    def crash(self) -> None:
        raise Exception("Not YET implemented for this flavour")

    def forward_port(self, host_port: int = 8080, guest_port: int = 80) -> None:
        raise Exception("Not YET implemented for this flavour")

    def block(self) -> None:
        raise Exception("Not YET implemented for this flavour")

    def unblock(self) -> None:
        """Make the machine reachable."""
        raise Exception("Not YET implemented for this flavour")

    # TODO move VM (pid)
    def release(self) -> None:
        raise Exception("Not YET implemented for this flavour")

    def run_callbacks(self) -> None:
        for callback in self.callbacks:
            callback()

    def direct_exec(self, user, name) -> None:
        raise Exception("Not YET implemented for this flavour")
