import time
from typing import List
from .driver.machine import Machine


class Flavour(object):
    name: str
    external_connect: bool = False
    machines: List[Machine] = []

    def __init__(self, ctx):
        self.ctx = ctx

    def check(self, state="running"):
        self.ctx.wlog(f"Check not implement for flavour: {self.name}")
        return -1

    def wait_on_check(self, state="running", mode="all", period=0.5, round=5):
        for _ in range(round):
            if mode == "all" and self.check(state) == len(self.machines):
                return True
            elif mode == "any" and self.check(state) > 0:
                return
            time.sleep(period)
        return False

    def generate_deployment_info(self, ssh_pub_key_file):
        pass

    def ext_connect(self, user, node, execute, ssh_key_file):
        pass


base_flavours = [
    {"name": "docker", "description": "Docker-Compose based", "image": {}},
    {
        "name": "g5k-image",
        "description": "Flavour for Grid'5000 platform",
        "image": {"distribution": "all-in-one", "type": "tarball"},
    },
    {
        "name": "g5k-nfs-store",
        "description": "Flavour for Grid'5000 platform",
        "image": {"distribution": "all-in-one", "type": "remote-store"},
    },
    {
        "name": "g5k-ramdisk",
        "description": "Flavour for Grid'5000 platform",
        "image": {"distribution": "all-in-one", "type": "ramdisk"},
    },
    {"name": "nspawn", "description": "Systemd-nspawn", "image": {}},
    {"name": "vm", "description": "vm", "image": {"distribution": "all-in-one"}},
    {
        "name": "vm-ramdisk",
        "description": "Plain vm ramdisk (all-in-memory), need lot of ram !",
        "image": {"distribution": "all-in-one", "type": "ramdisk"},
    },
]
