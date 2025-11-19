import os
import os.path as op
import subprocess
import click
import ipaddress
import socket

from ..flavour import Flavour
from ..actions import (
    read_compose_info,
    read_deployment_info,
    generate_deployment_info,
)

from ..driver.machine import Machine

# from ..default_role import DefaultRole

from typing import Tuple, Optional


def nft_nixos_fw_rules(ctx, remove=False, add=False):
    subprocess.call("sudo true", shell=True)
    check_process = ""
    try:
        check_process = subprocess.check_output(
            [
                "sudo",
                "nft",
                "--handle",
                "--numeric",
                "list",
                "chain",
                "ip",
                "filter",
                "nixos-fw",
            ],
            stderr=subprocess.DEVNULL,
        )

    except subprocess.CalledProcessError as e:
        ctx.wlog(f"nftable: ip chain filter not present, return code {e.returncode}")
        # print(f"{e.output} return code {e.returncode}")
        return -1  # non present

    nxc_br0_rule = False
    nxc_br0_rule_handle = -1
    for line in check_process.decode().rstrip("\n").splitlines():
        if 'iifname "nxc-br0"' in line:
            nxc_br0_rule = True
            s = line.split()
            if s[-2] == "handle":
                nxc_br0_rule_handle = s[-1]

    if remove and nxc_br0_rule:
        subprocess.Popen(
            [
                "sudo",
                "nft",
                "delete",
                "rule",
                "ip",
                "filter",
                "nixos-fw",
                "handle",
                nxc_br0_rule_handle,
            ]
        )
        return 1
    if add and not nxc_br0_rule:
        subprocess.Popen(
            [
                "sudo",
                "nft",
                "insert",
                "rule",
                "ip",
                "filter",
                "nixos-fw",
                'iifname "nxc-br0" counter packets 0 bytes 0 accept',
            ]
        )
        return 1
    return 0


def set_prefix_store_volumes(dc_json, prefix_store):
    for service in dc_json["services"].keys():
        volumes = dc_json["services"][service]["volumes"]
        volumes_out = []
        for vol in volumes:
            if "/nix/store" == vol[:10]:
                volumes_out.append(f"{prefix_store}{vol[4:]}")
            else:
                volumes_out.append(vol)
        dc_json["services"][service]["volumes"] = volumes_out


class NspawnFlavour(Flavour):
    nspawn_compose_file = None

    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "nspawn"
        self.description = "Systemd-nspawn container"

    @staticmethod
    def host_info(role, hostname, info):
        return {"role": role, "host": hostname, "toplevel": info["toplevel"]}

    def generate_deployment_info(self, ssh_pub_key_file):
        ctx = self.ctx
        deploy_dir = op.join(ctx.envdir, "deploy")
        if not op.exists(deploy_dir):
            create = click.style("   create", fg="green")
            ctx.log("   " + create + "  " + deploy_dir)
            os.mkdir(deploy_dir)

        if not ctx.ip_range:
            ctx.ip_range = "10.0.3.2,10.0.3.254"

        ip_l, ip_h = ctx.ip_range.split(",")
        subnets = ipaddress.summarize_address_range(
            ipaddress.IPv4Address(ip_l), ipaddress.IPv4Address(ip_h)
        )
        ctx.ip_addresses = [str(ip) for s in subnets for ip in s]

        # TODO ugly need to harmonisation build/composition_info through all flavours
        if not ctx.compose_info:
            read_compose_info(ctx)
        ctx.compose_info["roles"] = ctx.compose_info[ctx.composition_name]

        generate_deployment_info(ctx, ssh_pub_key_file)

    def driver_initialize(self, tmp_dir):
        print("TODO driver_initialize")
        exit
        assert self.ctx.deployment_info
        if not self.nspawn_compose_file:
            self.nspawn_compose_file = self.ctx.deployment_info["nspawn-compose-file"]

        nodes_names = self.ctx.deployment_info["nodes"]
        for name in nodes_names:
            self.machines.append(
                Machine(
                    self.ctx,
                    tmp_dir=tmp_dir,
                    start_command="",
                    name=name,
                )
            )

    def check(self, state="running"):
        print("TODO check")
        exit
        # check_process = subprocess.check_output(
        #     [
        #         "nspawn-compose",
        #         "-f",
        #         self.nspawn_compose_file,
        #         "ps",
        #         "--services",
        #         "--filter",
        #         f"status={state}",
        #     ],
        # )
        # return len(check_process.decode().rstrip("\n").splitlines())

    def connect(self, machine):
        if machine.connected:
            return
        self.start_all()

    def launch(self):
        ctx = self.ctx
        if not ctx.deployment_info:
            read_deployment_info(ctx)

        nest_host = ""

        if "nested" in ctx.deployment_info and ctx.deployment_info["nested"]:
            nest_host = f"-{socket.gethostname()}"

        # prepare nxc-dnsmasq.conf
        artifact_dir = op.join(
            ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
        )
        os.makedirs(artifact_dir, mode=0o700, exist_ok=True)
        nxc_dnsmasq_conf_file = op.join(artifact_dir, f"nxc-dnsmasq{nest_host}.conf")

        with open(nxc_dnsmasq_conf_file, "w") as outfile:
            for ip, host_info in ctx.deployment_info["deployment"].items():
                outfile.write(f"dhcp-host={host_info['host']},{ip}\n")

        _ROOT = os.path.abspath(os.path.dirname(__file__))
        nxc_net_script = _ROOT + "/nspawn/nxc-net.sh"
        machine_dir_script = _ROOT + "/nspawn/machine-dir.sh"

        env = os.environ

        ctx.log("Prepare and launch nspawn container")
        ctx.log("Test sudo (root privilege rights required)")
        subprocess.call("sudo true", shell=True)

        env["NXC_DHCP_CONFILE"] = nxc_dnsmasq_conf_file
        preserve_env = "NXC_DHCP_CONFILE"

        if "nested" in ctx.deployment_info and ctx.deployment_info["nested"]:
            nested_network = ctx.deployment_info["network"]
            net_addr, net_masq = nested_network.split("/")
            if net_masq != "24":
                ctx.elog("Netmask different from /24 is not supported")
            a, b, c, _ = net_addr.split(".")
            net_prefix = f"{a}.{b}.{c}"
            env["NXC_ADDR"] = f"{net_prefix}.1"
            env["NXC_NETWORK"] = nested_network
            env["NXC_DHCP_RANGE"] = f"{net_prefix}.2,{net_prefix}.254"
            preserve_env += ",NXC_ADDR,NXC_NETWORK,NXC_DHCP_RANGE"

        ctx.log("Launch nxc-net script")

        subprocess.Popen(
            ["sudo", f"--preserve-env={preserve_env}", nxc_net_script, "start"],
            env=env,
        )

        ctx.log("Check and adapt nftable nixos-fw chain if any")

        nft_nixos_fw_rules(ctx, add=True)

        ctx.log("Prepare machines dirs")
        p_lst = []
        for _, host_info in ctx.deployment_info["deployment"].items():
            p = subprocess.Popen(
                [
                    "sudo",
                    machine_dir_script,
                    "prepare",
                    host_info["host"],
                    host_info["toplevel"],
                ],
                stdout=subprocess.DEVNULL,
            )
            p_lst.append(p)

        for p in p_lst:
            p.wait()

        ctx.log("\nStart containers")
        p_lst = []

        env["SYSTEMD_NSPAWN_UNIFIED_HIERARCHY"] = "1"

        for _, host_info in ctx.deployment_info["deployment"].items():
            subprocess.Popen(
                [
                    "sudo",
                    "--preserve-env=SYSTEMD_NSPAWN_UNIFIED_HIERARCHY",
                    "systemd-nspawn",
                    "-bD",
                    f"/var/lib/machines/{host_info['host']}",
                    "--network-bridge=nxc-br0",
                ],
                env=env,
                # stdout=subprocess.DEVNULL,
                # stderr=subprocess.DEVNULL,
            )
            p_lst.append(p)
        for p in p_lst:
            p.wait()

    def start_all(self):
        print("TODO start_all")
        exit
        pass
        # if not self.external_connect:
        #     with rootlog.nested("starting nspawn-compose"):
        #         subprocess.Popen(
        #             ["nspawn-compose", "-f", self.nspawn_compose_file, "up", "-d"]
        #         )

        #     self.wait_on_check()

        # for machine in self.machines:
        #     if not machine.connected:
        #         self.start(machine)
        #         machine.connected = True

    def start(self, machine):  # TODO MOVE to Connect ???
        print("TODO start")
        exit
        pass
        assert machine.name
        assert self.nspawn_compose_file

        # machine.start_process_shell(
        #     [
        #         "nspawn-compose",
        #         "-f",
        #         self.nspawn_compose_file,
        #         "exec",
        #         "-u",
        #         "root",
        #         "-T",
        #         machine.name,
        #         "bash",
        #         "-l",
        #     ]
        # )

    def execute(
        self,
        machine,
        command: str,
        check_return: bool = True,
        timeout: Optional[int] = 900,
    ) -> Tuple[int, str]:
        return machine.execute_process_shell(command, check_return, timeout)

    def restart(self, machine):
        machine.restart_process_shell()

    def cleanup(self):
        ctx = self.ctx
        if not ctx.deployment_info:
            read_deployment_info(ctx)

        _ROOT = os.path.abspath(os.path.dirname(__file__))
        nxc_net_script = _ROOT + "/nspawn/nxc-net.sh"
        machine_dir_script = _ROOT + "/nspawn/machine-dir.sh"

        ctx.log("Stop and cleanup nspawn container(s)")
        ctx.log("Test sudo (root privilege rights required)")
        subprocess.call("sudo true", shell=True)

        for _, host_info in ctx.deployment_info["deployment"].items():
            subprocess.Popen(
                [
                    "sudo",
                    "machinectl",
                    "stop",
                    host_info["host"],
                ]
            )

        for _, host_info in ctx.deployment_info["deployment"].items():
            subprocess.Popen(
                [
                    "sudo",
                    machine_dir_script,
                    "remove",
                    host_info["host"],
                ]
            )
        ctx.log("Stop nxc-net")

        subprocess.Popen(["sudo", nxc_net_script, "stop"])
        ctx.log("Remove nftable chain nixos-fw if any")
        nft_nixos_fw_rules(ctx, remove=True)

    def shell_interact(self, machine) -> None:
        self.connect(machine)
        self.ext_connect("root", machine.name)

    def ext_connect(self, user, node, execute=True, ssh_key_file=None):
        # subprocess.call("sudo true", shell=True)
        cmd = f"machinectl shell {user}@{node}"
        if execute:
            return_code = subprocess.run(cmd, shell=True).returncode

            if return_code:
                self.ctx.wlog(f"Machinectl exit code is not null: {return_code}")
            return return_code
        else:
            return cmd
