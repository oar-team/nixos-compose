import os
import os.path as op
import json
import subprocess
import click
import copy

from ..flavour import Flavour
from ..actions import read_compose_info, realpath_prefix_from_store
from ..driver.logger import rootlog
from ..driver.machine import Machine
from ..default_role import DefaultRole

from typing import Tuple, Optional


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


def generate_docker_compose_file(ctx):
    base_docker_compose, prefix_store = realpath_prefix_from_store(
        ctx, ctx.compose_info["docker-compose-file"]
    )
    docker_compose_content = {"services": {}}
    nodes_info = {}

    artifact_dir = op.join(
        ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
    )
    os.makedirs(artifact_dir, mode=0o700, exist_ok=True)
    with open(base_docker_compose) as dc_file:
        dc_json = json.load(dc_file)
        if prefix_store:
            set_prefix_store_volumes(dc_json, prefix_store)

        roles_distribution = {}
        for role in ctx.compose_info["roles"]:
            if role in ctx.roles_distribution:
                roles_distribution[role] = ctx.roles_distribution[role]
            elif (
                "roles_distribution" in ctx.compose_info
                and role in ctx.compose_info["roles_distribution"]
            ):
                roles_distribution[role] = ctx.compose_info["roles_distribution"][role]
            else:
                roles_distribution[role] = 1

        # Add bind  deployment file inside containers
        deployment_file = op.join(
            ctx.envdir, f"deploy/{ctx.composition_flavour_prefix}.json"
        )

        deployment_symlink = op.join(artifact_dir, "deployment.json")
        if not os.path.islink(deployment_symlink):
            os.symlink(deployment_file, deployment_symlink)

        for service in dc_json["services"].values():
            (service["volumes"]).append(
                {
                    "type": "bind",
                    "source": deployment_symlink,
                    "target": "/etc/nxc/deployment.json",
                }
            )
        for role, distribution in roles_distribution.items():
            if type(distribution) is int:
                if distribution == 1:
                    hostname = f"{role}"
                    config = copy.copy(dc_json["services"][role])
                    config["hostname"] = hostname
                    docker_compose_content["services"][hostname] = config
                    nodes_info[hostname] = role
                else:
                    for i in range(1, distribution + 1):
                        hostname = f"{role}{i}"
                        config = copy.copy(dc_json["services"][role])
                        config["hostname"] = hostname
                        docker_compose_content["services"][hostname] = config
                        nodes_info[hostname] = role
            elif type(distribution) is list:
                for hostname in distribution:
                    config = copy.copy(dc_json["services"][role])
                    config["hostname"] = hostname
                    docker_compose_content["services"][hostname] = config
                    nodes_info[hostname] = role
            elif type(distribution) is DefaultRole:
                nb_min_nodes = distribution.nb_min_nodes
                ctx.log(
                    f"Docker: Using DefaultRole -> {nb_min_nodes} nodes for role '{role}'"
                )
                if nb_min_nodes == 1:
                    hostname = f"{role}"
                    config = copy.copy(dc_json["services"][role])
                    config["hostname"] = hostname
                    docker_compose_content["services"][hostname] = config
                    nodes_info[hostname] = role
                else:
                    for i in range(1, nb_min_nodes + 1):
                        hostname = f"{role}{i}"
                        config = copy.copy(dc_json["services"][role])
                        config["hostname"] = hostname
                        docker_compose_content["services"][hostname] = config
                        nodes_info[hostname] = role
            else:
                raise Exception("Unvalid type for specifying the roles of the nodes")
        dc_json.pop("services")
        docker_compose_content = docker_compose_content | dc_json

    artifact_dir = op.join(
        ctx.envdir, f"artifact/{ctx.composition_name}/{ctx.flavour.name}"
    )
    os.makedirs(artifact_dir, mode=0o700, exist_ok=True)

    docker_compose_path = op.join(artifact_dir, "docker-compose.json")

    with open(docker_compose_path, "w") as outfile:
        outfile.write(json.dumps(docker_compose_content))
    return docker_compose_path, nodes_info


def generate_deployment_info_docker(ctx):
    if not ctx.compose_info:
        read_compose_info(ctx)

    deploy_dir = op.join(ctx.envdir, "deploy")
    if not op.exists(deploy_dir):
        create = click.style("   create", fg="green")
        ctx.log("   " + create + "  " + deploy_dir)
        os.mkdir(deploy_dir)

    docker_compose_path, nodes_info = generate_docker_compose_file(ctx)

    deployment_info = ctx.deployment_info

    # "nodes": ctx.compose_info["nodes"],
    deployment_info["nodes"] = list(nodes_info.keys())
    # "deployment": {n: {"role": n} for n in ctx.compose_info["nodes"]},
    deployment_info["deployment"] = {
        node_name: {"role": role_name} for (node_name, role_name) in nodes_info.items()
    }
    deployment_info["docker-compose-file"] = docker_compose_path

    if "test_script" in ctx.compose_info:
        deployment_info["test_script"] = ctx.compose_info["test_script"]

    if "all" in ctx.compose_info:
        deployment_info["all"] = ctx.compose_info["all"]

    # TODO move to action.py and factorize w/ geenerate_deployment_info
    with open(
        op.join(deploy_dir, f"{ctx.composition_flavour_prefix}.json"), "w"
    ) as outfile:
        outfile.write(json.dumps(deployment_info, indent=2))

    return docker_compose_path


class DockerFlavour(Flavour):
    docker_compose_file = None

    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "docker"
        self.description = ""
        # TOR self.docker_processes = {}

    def generate_deployment_info(self, ssh_pub_key_file):
        self.docker_compose_file = generate_deployment_info_docker(self.ctx)

    def driver_initialize(self, tmp_dir):
        assert self.ctx.deployment_info
        if not self.docker_compose_file:
            self.docker_compose_file = self.ctx.deployment_info["docker-compose-file"]

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
        check_process = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                self.docker_compose_file,
                "ps",
                "--services",
                "--filter",
                f"status={state}",
            ],
        )
        return len(check_process.decode().rstrip("\n").splitlines())

    def connect(self, machine):
        if machine.connected:
            return
        self.start_all()

    def start_all(self):
        if not self.external_connect:
            with rootlog.nested("starting docker compose"):
                subprocess.Popen(
                    ["docker", "compose", "-f", self.docker_compose_file, "up", "-d"]
                )

            self.wait_on_check()

        for machine in self.machines:
            if not machine.connected:
                self.start(machine)
                machine.connected = True

    def start(self, machine):  # TODO MOVE to Connect ???
        assert machine.name
        assert self.docker_compose_file

        machine.start_process_shell(
            [
                "docker",
                "compose",
                "-f",
                self.docker_compose_file,
                "exec",
                "-u",
                "root",
                "-T",
                machine.name,
                "bash",
                "-l",
            ]
        )

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
        # TODO handle stdout/stderr
        if not self.docker_compose_file:
            self.docker_compose_file = self.ctx.deployment_info["docker-compose-file"]
        subprocess.Popen(
            [
                "docker",
                "compose",
                "-f",
                self.docker_compose_file,
                "down",
                "--remove-orphans",
            ]
        )

    def shell_interact(self, machine) -> None:
        self.connect(machine)
        self.ext_connect("root", machine.name)

    def ext_connect(self, user, node, execute=True, ssh_key_file=None):
        if not self.docker_compose_file:
            self.docker_compose_file = self.ctx.deployment_info["docker-compose-file"]

        cmd = f"docker compose -f {self.docker_compose_file} exec -u {user} {node} bash"
        print(f"ext_connect {cmd}")
        if execute:
            return_code = subprocess.run(cmd, shell=True).returncode

            if return_code:
                self.ctx.wlog(f"Docker exit code is not null: {return_code}")
            return return_code
        else:
            return cmd
