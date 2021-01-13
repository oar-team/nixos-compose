from contextlib import contextmanager, _GeneratorContextManager
from queue import Queue, Empty
from typing import Tuple, Any, Callable, Dict, Iterator, Optional, List
from xml.sax.saxutils import XMLGenerator
import queue
import io
import _thread
import argparse
import atexit
import base64
import codecs
import os
import pathlib
import ptpython.repl
import pty
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
import json
from os import path
from base64 import b64encode


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

# Forward references
log: "Logger"
machines: "List[Machine]"
machines_ips: "List[str]"
mode: "Dict[str, Any]"


def eprint(*args: object, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def make_command(args: list) -> str:
    return " ".join(map(shlex.quote, (map(str, args))))


def create_log():
    global log
    log = Logger()


def create_vlan(vlan_nr: str) -> Tuple[str, str, "subprocess.Popen[bytes]", Any]:
    global log

    # sudo vde_switch -tap tap0 -s $QEMU_VDE_SOCKET --dirmode 0770 --group users&
    # sudo ip addr add 10.0.2.1/24 dev tap0
    # sudo ip link set dev tap0 up
    # slirpvde -d -s $QEMU_VDE_SOCKET  -dhcp

    log.log(
        "starting VDE switch for network {}, with tap0 (sudo required)".format(vlan_nr)
    )
    vde_socket = tempfile.mkdtemp(
        prefix="nixos-compose-vde-", suffix="-vde{}.ctl".format(vlan_nr)
    )

    log.log("need sudo to create tap0 interface")
    log.log(f"vde_socket: {vde_socket}")

    subprocess.call("sudo true", shell=True)

    vde_cmd = [
        "sudo",
        "vde_switch",
        "-tap",
        "tap0",
        "-s",
        vde_socket,
        "--dirmode",
        "0700",
        "--group",
        "users",
    ]
    log.log(f"vde_cmd: {' '.join(vde_cmd)}")

    pty_master, pty_slave = pty.openpty()
    vde_process = subprocess.Popen(
        [
            "sudo",
            "vde_switch",
            "-tap",
            "tap0",
            "-s",
            vde_socket,
            "--dirmode",
            "0770",
            "--group",
            "users",
        ],
        stdin=pty_slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    fd = os.fdopen(pty_master, "w")
    fd.write("version\n")
    # TODO: perl version checks if this can be read from
    # an if not, dies. we could hang here forever. Fix it.
    assert vde_process.stdout is not None
    vde_process.stdout.readline()
    if not os.path.exists(os.path.join(vde_socket, "ctl")):
        raise Exception("cannot start vde_switch")

    # setup tap0
    log.log("setup tap0 interface")
    # TODO add error handling
    subprocess.call("sudo ip addr add 10.0.2.1/24 dev tap0", shell=True)
    subprocess.call("sudo ip link set dev tap0 up", shell=True)

    # launch slirp
    log.log(f"slirpvde -d -s {vde_socket} -dhcp -q")
    # subprocess.call(f'slirpvde -d -s {vde_socket} -dhcp -q', shell=True)
    slirpvde_process = subprocess.Popen(
        f"slirpvde -d -s {vde_socket} -dhcp -q",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )
    # slirpvde_process = None
    return (vlan_nr, vde_socket, vde_process, fd, slirpvde_process)


def retry(fn: Callable) -> None:
    """Call the given function repeatedly, with 1 second intervals,
    until it returns True or a timeout is reached.
    """

    for _ in range(900):
        if fn(False):
            return
        time.sleep(1)
        print("retry")
    if not fn(True):
        raise Exception("action timed out")


class Logger:
    def __init__(self) -> None:
        self.logfile = os.environ.get("LOGFILE", "/dev/null")
        self.logfile_handle = codecs.open(self.logfile, "wb")
        self.xml = XMLGenerator(self.logfile_handle, encoding="utf-8")
        self.queue: "Queue[Dict[str, str]]" = Queue()

        self.xml.startDocument()
        self.xml.startElement("logfile", attrs={})

    def close(self) -> None:
        self.xml.endElement("logfile")
        self.xml.endDocument()
        self.logfile_handle.close()

    def sanitise(self, message: str) -> str:
        return "".join(ch for ch in message if unicodedata.category(ch)[0] != "C")

    def maybe_prefix(self, message: str, attributes: Dict[str, str]) -> str:
        if "machine" in attributes:
            return "{}: {}".format(attributes["machine"], message)
        return message

    def log_line(self, message: str, attributes: Dict[str, str]) -> None:
        self.xml.startElement("line", attributes)
        self.xml.characters(message)
        self.xml.endElement("line")

    def log(self, message: str, attributes: Dict[str, str] = {}) -> None:
        eprint(self.maybe_prefix(message, attributes))
        self.drain_log_queue()
        self.log_line(message, attributes)

    def enqueue(self, message: Dict[str, str]) -> None:
        self.queue.put(message)

    def drain_log_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                attributes = {"machine": item["machine"], "type": "serial"}
                self.log_line(self.sanitise(item["msg"]), attributes)
        except Empty:
            pass

    @contextmanager
    def nested(self, message: str, attributes: Dict[str, str] = {}) -> Iterator[None]:
        eprint(self.maybe_prefix(message, attributes))

        self.xml.startElement("nest", attrs={})
        self.xml.startElement("head", attributes)
        self.xml.characters(message)
        self.xml.endElement("head")

        tic = time.time()
        self.drain_log_queue()
        yield
        self.drain_log_queue()
        toc = time.time()
        self.log("({:.2f} seconds)".format(toc - tic))

        self.xml.endElement("nest")


class Machine:
    def __init__(self, args: Dict[str, Any]) -> None:
        if "name" in args:
            self.name = args["name"]
        else:
            self.name = "machine"
            cmd = args.get("startCommand", None)
            if cmd:
                match = re.search("run-(.+)-vm$", cmd)
                if match:
                    self.name = match.group(1)
        self.logger = args["log"]
        self.script = args.get("startCommand", self.create_startcommand(args))

        tmp_dir = os.environ.get("TMPDIR", tempfile.gettempdir())

        def create_dir(name: str) -> str:
            path = os.path.join(tmp_dir, name)
            os.makedirs(path, mode=0o700, exist_ok=True)
            return path

        self.state_dir = os.path.join(tmp_dir, f"vm-state-{self.name}")
        if not args.get("keepVmState", False):
            self.cleanup_statedir()
        os.makedirs(self.state_dir, mode=0o700, exist_ok=True)
        self.shared_dir = create_dir("shared-xchg")

        self.booted = False
        self.connected = False
        self.pid: Optional[int] = None
        self.socket = None
        self.monitor: Optional[socket.socket] = None
        self.allow_reboot = args.get("allowReboot", False)
        if "vm_id" in args:
            self.vm_id = args["vm_id"]
            self.ip = args["ip"]
        if "init" in args:
            self.init = args["init"]

    # TOREMOVE OR ADAPT
    @staticmethod
    def create_startcommand(args: Dict[str, str]) -> str:
        net_backend = "-netdev user,id=net0"
        net_frontend = "-device virtio-net-pci,netdev=net0"

        if "netBackendArgs" in args:
            net_backend += "," + args["netBackendArgs"]

        if "netFrontendArgs" in args:
            net_frontend += "," + args["netFrontendArgs"]

        start_command = (
            "qemu-kvm -m 384 " + net_backend + " " + net_frontend + " $QEMU_OPTS "
        )

        if "hda" in args:
            hda_path = os.path.abspath(args["hda"])
            if args.get("hdaInterface", "") == "scsi":
                start_command += (
                    "-drive id=hda,file="
                    + hda_path
                    + ",werror=report,if=none "
                    + "-device scsi-hd,drive=hda "
                )
            else:
                start_command += (
                    "-drive file="
                    + hda_path
                    + ",if="
                    + args["hdaInterface"]
                    + ",werror=report "
                )

        if "cdrom" in args:
            start_command += "-cdrom " + args["cdrom"] + " "

        if "usb" in args:
            start_command += (
                "-device piix3-usb-uhci -drive "
                + "id=usbdisk,file="
                + args["usb"]
                + ",if=none,readonly "
                + "-device usb-storage,drive=usbdisk "
            )
        if "bios" in args:
            start_command += "-bios " + args["bios"] + " "

        start_command += args.get("qemuFlags", "")

        return start_command

    def is_up(self) -> bool:
        return self.booted and self.connected

    def log(self, msg: str) -> None:
        self.logger.log(msg, {"machine": self.name})

    def nested(self, msg: str, attrs: Dict[str, str] = {}) -> _GeneratorContextManager:
        my_attrs = {"machine": self.name}
        my_attrs.update(attrs)
        return self.logger.nested(msg, my_attrs)

    def wait_for_monitor_prompt(self) -> str:
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
        message = ("{}\n".format(command)).encode()
        self.log("sending monitor command: {}".format(command))
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

    def execute(self, command: str) -> Tuple[int, str]:
        self.connect()

        out_command = "( {} ); echo '|!=EOF' $?\n".format(command)
        self.shell.send(out_command.encode())

        output = ""
        status_code_pattern = re.compile(r"(.*)\|\!=EOF\s+(\d+)")

        while True:
            chunk = self.shell.recv(4096).decode(errors="ignore").replace("\r", "")
            # print(chunk)
            match = status_code_pattern.match(chunk)
            if match:
                output += match[1]
                status_code = int(match[2])
                return (status_code, output)
            output += chunk

    def succeed(self, *commands: str) -> str:
        """Execute each command and check that it succeeds."""
        output = ""
        for command in commands:
            with self.nested("must succeed: {}".format(command)):
                (status, out) = self.execute(command)
                if status != 0:
                    self.log("output: {}".format(out))
                    raise Exception(
                        "command `{}` failed (exit code {})".format(command, status)
                    )
                output += out
        return output

    def fail(self, *commands: str) -> str:
        """Execute each command and check that it fails."""
        output = ""
        for command in commands:
            with self.nested("must fail: {}".format(command)):
                (status, out) = self.execute(command)
                if status == 0:
                    raise Exception(
                        "command `{}` unexpectedly succeeded".format(command)
                    )
                output += out
        return output

    def wait_until_succeeds(self, command: str) -> str:
        """Wait until a command returns success and return its output.
        Throws an exception on timeout.
        """
        output = ""

        def check_success(_: Any) -> bool:
            nonlocal output
            status, output = self.execute(command)
            return status == 0

        with self.nested("waiting for success: {}".format(command)):
            retry(check_success)
            return output

    def wait_until_fails(self, command: str) -> str:
        """Wait until a command returns failure.
        Throws an exception on timeout.
        """
        output = ""

        def check_failure(_: Any) -> bool:
            nonlocal output
            status, output = self.execute(command)
            return status != 0

        with self.nested("waiting for failure: {}".format(command)):
            retry(check_failure)
            return output

    def wait_for_shutdown(self) -> None:
        if not self.booted:
            return

        with self.nested("waiting for the VM to power off"):
            sys.stdout.flush()
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

        with self.nested("waiting for the VM to finish booting"):
            tic = time.time()
            self.start()
            if mode["shell"] == "chardev":
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
        host_src = pathlib.Path(source)
        vm_target = pathlib.Path(target)
        with tempfile.TemporaryDirectory(dir=self.shared_dir) as shared_td:
            shared_temp = pathlib.Path(shared_td)
            host_intermediate = shared_temp / host_src.name
            vm_shared_temp = pathlib.Path("/tmp/shared") / shared_temp.name
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
        out_dir = pathlib.Path(os.environ.get("out", os.getcwd()))
        vm_src = pathlib.Path(source)
        with tempfile.TemporaryDirectory(dir=self.shared_dir) as shared_td:
            shared_temp = pathlib.Path(shared_td)
            vm_shared_temp = pathlib.Path("/tmp/shared") / shared_temp.name
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
        """Debugging: Dump the contents of the TTY<n>
        """
        self.execute("fold -w 80 /dev/vcs{} | systemd-cat".format(tty))

    def wait_for_console_text(self, regex: str) -> None:
        self.log("waiting for {} to appear on console".format(regex))
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

    def start(self, ordered=False) -> None:
        if self.booted:
            return

        if mode["vm"] and not ordered:
            self.log("WARNNING: mapping @ip-role can be WRONG (hint: use start_all())")

        self.log("starting vm")

        def create_socket(path: str) -> socket.socket:
            if os.path.exists(path):
                os.unlink(path)
            s = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
            s.bind(path)
            s.listen(1)
            return s

        print("monitor")
        monitor_path = os.path.join(self.state_dir, "monitor")
        self.monitor_socket = create_socket(monitor_path)
        print("shell")
        self.shell_path = os.path.join(self.state_dir, "shell")
        # self.shell_socket = create_socket("/tmp/" + self.name + ".sock")
        self.shell_socket = create_socket(self.shell_path)

        dev_shell = ""
        if mode["shell"] == "chardev":
            dev_shell = " -chardev socket,id=shell,path={}".format(self.shell_path)
            dev_shell += " -device virtconsole,chardev=shell"

        qemu_options = (
            " ".join(
                [
                    "" if self.allow_reboot else "-no-reboot",
                    "-monitor unix:{}".format(monitor_path),
                    "-device virtio-serial",
                    "-device virtio-rng-pci",
                    "-serial stdio" if "DISPLAY" in os.environ else "-nographic",
                ]
            )
            + dev_shell
            + " "
            + os.environ.get("QEMU_OPTS", "")
        )

        environment = dict(os.environ)
        environment.update(
            {
                "TMPDIR": self.state_dir,
                "SHARED_DIR": self.shared_dir,
                "USE_TMPDIR": "1",
                # "QEMU_VDE_SOCKET": self.vde_process, TOREMOVE
                "QEMU_OPTS": qemu_options,
                # "DEPLOY": "1",
                "VM_ID": str(self.vm_id),
                "ROLE": f"role={self.name}",
            }
        )
        if mode["image"]["distribution"] == "all-in-one":
            environment["INIT"] = self.init

        # print(self.script)
        print("process")
        self.process = subprocess.Popen(
            self.script,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=self.state_dir,
            env=environment,
        )
        print("accept monitor")
        self.monitor, _ = self.monitor_socket.accept()
        print("accept shell")
        if mode["shell"] == "chardev":
            self.shell, _ = self.shell_socket.accept()

        print("after accept")
        # Store last serial console lines for use
        # of wait_for_console_text
        self.last_lines: Queue = Queue()

        def process_serial_output() -> None:
            assert self.process.stdout is not None
            for _line in self.process.stdout:
                # Ignore undecodable bytes that may occur in boot menus
                line = _line.decode(errors="ignore").replace("\r", "").rstrip()
                self.last_lines.put(line)
                eprint("{} # {}".format(self.name, line))
                self.logger.enqueue({"msg": line, "machine": self.name})

        _thread.start_new_thread(process_serial_output, ())

        print("wait_for_monitor_prompt()")
        self.wait_for_monitor_prompt()

        self.pid = self.process.pid
        self.booted = True
        self.log("QEMU running (pid {})".format(self.pid))

    def socat(self) -> None:
        socat_cmd = "socat UNIX-CONNECT:{} EXEC:'ssh -o StrictHostKeyChecking=no root@{}' &".format(
            self.shell_path, self.ip
        )
        subprocess.call(socat_cmd, shell=True)
        self.shell, _ = self.shell_socket.accept()

    def cleanup_statedir(self) -> None:
        if os.path.isdir(self.state_dir):
            shutil.rmtree(self.state_dir)
            self.logger.log(f"deleting VM state directory {self.state_dir}")
            self.logger.log("if you want to keep the VM state, pass --keep-vm-state")

    def shutdown(self) -> None:
        if not self.booted:
            return

        self.shell.send("poweroff\n".encode())
        self.wait_for_shutdown()

    def crash(self) -> None:
        if not self.booted:
            return

        self.log("forced crash")
        self.send_monitor_command("quit")
        self.wait_for_shutdown()

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
        """Make the machine reachable.
        """
        self.send_monitor_command("set_link virtio-net-pci.1 on")


def create_machine(args: Dict[str, Any]) -> Machine:
    global log
    args["log"] = log
    args["redirectSerial"] = os.environ.get("USE_SERIAL", "0") == "1"
    return Machine(args)


def start_all() -> None:
    global machines
    global machines_ips

    with log.nested("starting all VMs"):
        for machine in machines:
            machine.start(ordered=True)  # ADD nowait_shell
            if mode["vm"] and mode["image"]["distribution"] != ["all-in-one"]:
                time.sleep(
                    1.5
                )  # TODO UGLY (wait dhcp's ip attribution) -> need static mapping ip/role


def join_all() -> None:
    global machines
    with log.nested("waiting for all VMs to finish"):
        for machine in machines:
            machine.wait_for_shutdown()


def test_script() -> None:
    exec(os.environ["testScript"])


def run_tests() -> None:
    global machines
    tests = os.environ.get("tests", None)
    if tests is not None:
        with log.nested("running the VM test script"):
            try:
                exec(tests, globals())
            except Exception as e:
                eprint("error: ")
                traceback.print_exc()
                sys.exit(1)
    else:
        ptpython.repl.embed(locals(), globals())

    # TODO: Collect coverage data

    for machine in machines:
        if machine.is_up():
            machine.execute("sync")


@contextmanager
def subtest(name: str) -> Iterator[None]:
    with log.nested(name):
        try:
            yield
            return True
        except Exception as e:
            log.log(f'Test "{name}" failed with error: "{e}"')
            raise e

    return False


def check_ssh_port(hosts):
    nb_hosts = len(hosts)
    nmap_cmd = "nmap -Pn -p22 {} -oG - | grep '22/open' | wc -l".format(" ".join(hosts))
    log.log("Scan machines ssh port")
    while True:
        o = subprocess.check_output(nmap_cmd, shell=True)
        if int(o.rstrip().decode()) == nb_hosts:
            break
        print(".", end="")
        time.sleep(0.2)
    print("")
    log.log("All ssh ports are ready")


def driver_mode(driver_mode, flavour, deployment, driver_repl, test_script=None):

    global mode
    mode = driver_mode
    assert "vm" in driver_mode
    assert "image" in flavour

    mode["image"] = flavour["image"]

    global machines
    machines = []

    create_log()
    # create vde vlan
    log.log(mode["name"])

    if mode["vm"]:
        vde_vlan = create_vlan("0")
        vde_socket = vde_vlan[1]
        os.environ["QEMU_VDE_SOCKET"] = vde_socket

    # TODO reduce deployment_info (remove keys vm_id qemu_script)
    # deployment_info_str = json.dumps(deployment, separators=(',', ':'))
    # qemu_append = ""
    # if "ssh_key.pub" in deployment:
    #     ssh_key_pub_b64 = b64encode(deployment["ssh_key.pub"].encode()).decode()
    #     qemu_append = "ssh_key.pub:" + ssh_key_pub_b64
    #     deployment.pop("ssh_key.pub")

    deployment_info_str = json.dumps(deployment)
    deploy_info_b64 = b64encode(deployment_info_str.encode()).decode()

    if len(deploy_info_b64) > (4096 - 256):
        log.log(
            "The base64 encoded deploy data is too large: use an http server to serve it"
        )
        sys.exit(1)

    # os.environ["QEMU_APPEND"] = qemu_append
    base_qemu_script = None
    os.environ["DEPLOY"] = f"deploy:{deploy_info_b64}"
    if mode["image"]["distribution"] == "all-in-one":
        os.environ["KERNEL"] = deployment["all"]["kernel"]
        os.environ["INITRD"] = deployment["all"]["initrd"]
        base_qemu_script = deployment["all"]["qemu_script"]

    ips = []
    for i in range(len(deployment["deployment"])):
        ip = "10.0.2.{}".format(15 + i)
        ips.append(ip)
        if ip not in deployment["deployment"]:
            log.log(f"In vm mode, {ip} must be present")
            sys.exit(1)
        v = deployment["deployment"][ip]

        name = v["role"]

        if base_qemu_script:
            qemu_script = base_qemu_script
        else:
            qemu_script = v["qemu_script"]

        machines.append(
            create_machine(
                {
                    "name": name,
                    "startCommand": qemu_script,
                    "ip": ip,
                    "vm_id": v["vm_id"],
                    "keepVmState": False,
                    "init": v["init"],
                }
            )
        )

    machine_eval = [
        "{0} = machines[{1}]".format(m.name, idx) for idx, m in enumerate(machines)
    ]

    @atexit.register
    def clean_up() -> None:
        with log.nested("cleaning up"):
            for machine in machines:
                if machine.pid is None:
                    continue
                log.log("killing {} (pid {})".format(machine.name, machine.pid))
                # machine.process.kill()
                os.kill(machine.process.pid, signal.SIGSTOP)

        log.close()

    exec("\n".join(machine_eval), globals())

    start_all()
    check_ssh_port(ips)

    if mode["shell"] == "ssh":
        for machine in machines:
            print("create socat link: {}".format(machine.name))
            machine.socat()

    if test_script is not None and not driver_repl:
        tic = time.time()
        with log.nested("running the VM test script"):
            # start machines in ascending order of Ips (to match ip/role distribution
            # done by slirp-vde's dhcp
            try:
                exec(test_script, globals())
            except Exception as e:
                eprint("error: ")
                traceback.print_exc()
                sys.exit(1)
        log.log("test script ended")
        toc = time.time()
        print("test script finished in {:.2f}s".format(toc - tic))

    else:
        if test_script:
            os.environ["testScript"] = test_script
        ptpython.repl.embed(locals(), globals())

    sys.exit(0)
