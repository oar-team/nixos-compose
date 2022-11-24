from pathlib import Path
import io
import os
import pty
import sys
import shutil
import subprocess

from .logger import rootlog


class VLan:
    """This class handles a VLAN that the run-vm scripts identify via its
    number handles. The network's lifetime equals the object's lifetime.
    """

    nr: int
    socket_dir: Path

    process: subprocess.Popen
    slirpvde_process: subprocess.Popen
    pid: int
    fd: io.TextIOBase

    def __repr__(self) -> str:
        return f"<Vlan Nr. {self.nr}>"

    def __init__(self, nr: int, tmp_dir: Path, ctx):
        self.ctx = ctx
        self.nr = nr
        self.socket_dir = tmp_dir / f"vde{self.nr}.ctl"

        # TODO: don't side-effect environment here
        os.environ[f"QEMU_VDE_SOCKET_{self.nr}"] = str(self.socket_dir)

        rootlog.info("start vlan")
        pty_master, pty_slave = pty.openpty()

        if not shutil.which("vde_switch"):
            ctx.elog("vde_switch not found, please install vde2")
            sys.exit(1)

        vde_cmd = ["vde_switch"]

        if ctx.vde_tap:
            rootlog.info(
                f"starting VDE switch for network {self.nr}, with tap0 (sudo required)"
            )
            subprocess.call("sudo true", shell=True)
            vde_cmd = ["sudo"] + vde_cmd + ["-tap", "tap0"]

        group_users = "users"
        if ctx.platform and ctx.platform.group_users:
            group_users = ctx.platform.group_users
        vde_cmd = vde_cmd + [
            "-s",
            self.socket_dir,
            "-mod",
            "0770",
            "-group",
            group_users,
        ]

        self.process = subprocess.Popen(
            vde_cmd,
            stdin=pty_slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        self.pid = self.process.pid
        self.fd = os.fdopen(pty_master, "w")
        self.fd.write("version\n")

        # TODO: perl version checks if this can be read from
        # an if not, dies. we could hang here forever. Fix it.
        assert self.process.stdout is not None
        self.process.stdout.readline()
        if not (self.socket_dir / "ctl").exists():
            rootlog.error("cannot start vde_switch")

        # setup tap0
        if ctx.vde_tap:
            rootlog.info("setup tap0 interface")
            # TODO add error handling
            subprocess.call("sudo ip addr add 10.0.2.1/24 dev tap0", shell=True)
            subprocess.call("sudo ip link set dev tap0 up", shell=True)

            # launch slirp
            rootlog.info(f"slirpvde -d -s {self.socket_dir} -dhcp -q")
            # subprocess.call(f'slirpvde -d -s {vde_socket} -dhcp -q', shell=True)
            slirpvde_process = subprocess.Popen(
                f"slirpvde -d -s {self.socket_dir} -dhcp -q",
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            self.slirpvde_process = slirpvde_process
            rootlog.info(f"running slirpvde (pid {slirpvde_process.pid})")

        rootlog.info(f"running vlan (pid {self.pid})")

    def __del__(self) -> None:
        rootlog.info(f"kill vlan (pid {self.pid})")
        self.fd.close()
        self.process.terminate()
        if self.slirpvde_process:
            self.slirpvde_process.terminate()
