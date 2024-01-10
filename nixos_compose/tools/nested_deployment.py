#!/usr/bin/env python
import argparse
import json
import os
import os.path as op
import sys


def get_ssh_pub_key(ssh_pub_key_file):
    if not ssh_pub_key_file:
        ssh_pub_key_file = os.environ["HOME"] + "/.ssh/id_rsa.pub"
    with open(ssh_pub_key_file, "r") as f:
        sshkey_pub = f.read().rstrip()
    return sshkey_pub


def realpath_from_store(path, include_prefix_store=False):
    p = op.realpath(path)
    for store_path in [
        f"{os.environ['HOME']}/.local/share/nix/root/nix",
        f"{os.environ['HOME']}/.nix",
    ]:
        new_p = f"{store_path}{p[4:]}"
        if op.exists(new_p):
            if include_prefix_store:
                return new_p, store_path
            else:
                return new_p
    if op.exists(p):
        if include_prefix_store:
            return p, None
        else:
            return p
    print(f"{path} does not exist in standard store or alternate", file=sys.stderr)
    sys.exit(1)


def read_role_distribution(role_distribution_file):
    with open(role_distribution_file, "r") as f:
        role_distribution = json.load(f)
    return role_distribution


def nested_deployment(composition, role_distribution, hostbase_filter=None):
    # import pdb; pdb.set_trace()
    deployment_info = {}
    ip_hosts = []
    route_commands = []
    net_index = 0
    host_index = 1
    network = ""

    for hostbase, v in role_distribution["role_distribution"].items():
        nest_host_index = 1
        l, h = v["range"].split("-")
        for host_index in range(int(l), int(h) + 1):
            host = f"{hostbase}{host_index}"
            role = v["role"]
            folding = v["folding"]
            toplevel = composition[role]["toplevel"]

            print(f"host: {host}, role: {role}, folding: {folding}")
            for i in range(1, int(folding) + 1):
                ip = f"10.0.{3 + net_index}.{1 + i}"
                nested_host = f"{role}{nest_host_index}"
                print(f"    {nested_host} : {ip}")
                nest_host_index += 1
                if not hostbase_filter or (hostbase_filter == host):
                    if hostbase_filter:
                        print(f"{host}:")
                    deployment_info[ip] = {
                        "role": role,
                        "host": nested_host,
                        "toplevel": toplevel,
                    }
                ip_hosts.append(f"{ip} {nested_host}")

            if hostbase_filter:
                if hostbase_filter != host:
                    route_commands.append(
                        f"ip route add 10.0.{3 + net_index}.0/24 via $(getent hosts {host} | cut -d' ' -f1)"
                    )
                else:
                    network = f"10.0.{3 + net_index}.0/24"
            net_index += 1
    return deployment_info, ip_hosts, route_commands, network


# role_distribution = read_role_distribution("nested_role_distribution.json")

# # deployment = nested_deployment("toplevel")
# # json_formatted_str = json.dumps(deployment, indent=2)
# # print(json_formatted_str)

# deployment, ip_hosts  = nested_deployment("toplevel", "foo1")
# json_formatted_str = json.dumps(deployment, indent=2)
# print(json_formatted_str)


# for ip_host in ip_hosts:
#     print(ip_host)
def parse_args(options):
    parser = argparse.ArgumentParser(
        description="Configs generator for nested deployment"
    )
    parser.add_argument(
        "-n",
        "--nested_role-distribution",
        type=str,
        default="nested_role_distribution.json",
    )
    parser.add_argument("--host", type=str, help="Hostname configuration target")
    parser.add_argument(
        "-d", "--deployment", type=str, help="Generated deploment name file"
    )
    parser.add_argument("-c", "--composition-info", type=str)
    parser.add_argument("--composition-name", type=str, default="composition")
    parser.add_argument(
        "-e",
        "--ip-hosts",
        type=str,
        help="Generated ip host tuple file (for /etc/hosts)",
    )
    parser.add_argument(
        "-i",
        "--ssh_pub_key_file",
        type=str,
        help="sshkey pub file (default ~/.ssh/id_rsa.pub)",
    )
    parser.add_argument(
        "-r", "--route-commands", type=str, help="Generated list off ip route commandes"
    )
    args = parser.parse_args(options)

    return args


# todo do we need host to nested table for ssh jump ?
def main(options=None):
    composition = {}

    inputs = parse_args(options)

    # read nested_role_
    role_distribution = read_role_distribution(inputs.nested_role_distribution)
    # import pdb; pdb.set_trace()
    #
    if inputs.composition_info:
        with open(realpath_from_store(inputs.composition_info), "r") as f:
            all_composition_info = json.load(f)
        composition = all_composition_info[inputs.composition_name]
    else:
        print("Composition info files is required")
        sys.exit(1)

    deployment_info, ip_hosts, route_commands, network = nested_deployment(
        composition, role_distribution, inputs.host
    )

    deployment = {
        "ssh_key.pub": get_ssh_pub_key(inputs.ssh_pub_key_file),
        "deployment": deployment_info,
        "composition": inputs.composition_name,
        "user": os.environ["USER"],
        "nested": True,
        "network": network,
    }

    if inputs.deployment:
        json_deployment = json.dumps(deployment, indent=2)
        with open(inputs.deployment, "w") as outfile:
            outfile.write(json_deployment)

    if inputs.ip_hosts:
        with open(inputs.ip_hosts, "w") as outfile:
            for ip_host in ip_hosts:
                outfile.write(ip_host + "\n")

    if inputs.route_commands:
        with open(inputs.route_commands, "w") as outfile:
            for route_command in route_commands:
                outfile.write(route_command + "\n")


if __name__ == "__main__":
    main()
