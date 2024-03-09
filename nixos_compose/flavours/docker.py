import os
import os.path as op
import json
import subprocess
import click
import copy

from ..flavour import Flavour
from ..actions import read_compose_info, realpath_from_store
from ..driver.logger import rootlog
from ..driver.machine import Machine
from ..driver.driver import Driver
from ..default_role import DefaultRole

from typing import List


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
    base_docker_compose, prefix_store = realpath_from_store(
        ctx, ctx.compose_info["docker-compose-file"], include_prefix_store=True
    )
    docker_compose_content = {"services": {}}
    nodes_info = {}

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
        for service in dc_json["services"].values():
            (service["volumes"]).append(
                {
                    "type": "bind",
                    "source": deployment_file,
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


class DockerMachine(Machine):
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

    def start(self) -> None:
        assert self.name
        assert DockerFlavour.docker_compose_file

        if self.booted:
            return

        if not DockerDriver.containers_launched:
            DockerFlavour.driver.launch_containers()

        self.shell = subprocess.Popen(
            [
                "docker-compose",
                "-f",
                DockerFlavour.docker_compose_file,
                "exec",
                "-u",
                "root",
                "-T",
                self.name,
                "bash",
                "-l",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.connected = True
        self.booted = True

    def shell_interact(self) -> None:
        self.connect()
        DockerFlavour.driver.default_connect("root", self.name)

    def release(self) -> None:
        raise Exception("Not YET implemented for this flavour")


class DockerDriver(Driver):
    containers_launched: bool

    def __init__(self, ctx, start_scripts, tests, keep_vm_state):
        DockerDriver.containers_launched = False

        tmp_dir = super().__init__(ctx, start_scripts, tests, keep_vm_state)

        assert self.ctx.deployment_info
        DockerFlavour.docker_compose_file = self.ctx.deployment_info[
            "docker-compose-file"
        ]

        # Replace to driver.__init__ ???
        # tmp_dir = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
        # tmp_dir.mkdir(mode=0o700, exist_ok=True)

        nodes_names = self.ctx.deployment_info["nodes"]
        for name in nodes_names:
            self.machines.append(
                DockerMachine(
                    self.ctx,
                    tmp_dir=tmp_dir,
                    start_command="",
                    name=name,
                )
            )

    def check(self, state="running"):
        check_process = subprocess.check_output(
            [
                "docker-compose",
                "-f",
                DockerFlavour.docker_compose_file,
                "ps",
                "--services",
                "--filter",
                f"status={state}",
            ],
        )
        return len(check_process.decode().rstrip("\n").splitlines())

    def launch_containers(self):
        if not DockerDriver.containers_launched:
            with rootlog.nested("Starting docker-compose"):
                subprocess.Popen(
                    [
                        "docker-compose",
                        "-f",
                        DockerFlavour.docker_compose_file,
                        "up",
                        "-d",
                    ]
                )
            self.wait_on_check()

            for machine in self.machines:
                machine.booted = True

            DockerDriver.containers_launched = True

    def start_all(self):
        if not DockerDriver.containers_launched:
            self.launch_containers()

        # No lazy process_shell creation
        super().start_all()  # Will create a process_shell per machine

    def cleanup(self):
        # TODO handle stdout/stderr
        if not DockerFlavour.docker_compose_file:
            DockerFlavour.docker_compose_file = self.ctx.deployment_info[
                "docker-compose-file"
            ]
        subprocess.Popen(
            [
                "docker-compose",
                "-f",
                DockerFlavour.docker_compose_file,
                "down",
                "--remove-orphans",
            ]
        )

    def default_connect(self, user, machine, execute=True, ssh_key_file=None):
        if not DockerFlavour.docker_compose_file:
            DockerFlavour.docker_compose_file = self.ctx.deployment_info[
                "docker-compose-file"
            ]

        cmd = f"docker-compose -f {DockerFlavour.docker_compose_file} exec -u {user} {machine} bash"
        # print(f"ext_connect {cmd}")
        if execute:
            return_code = subprocess.run(cmd, shell=True).returncode

            if return_code:
                self.ctx.wlog(f"Docker exit code is not null: {return_code}")
            return return_code
        else:
            return cmd


class DockerFlavour(Flavour):
    docker_compose_file = None
    driver = None

    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "docker"
        self.description = ""
        # TOR self.docker_processes = {}

    def generate_deployment_info(self, ssh_pub_key_file=None):
        DockerFlavour.docker_compose_file = generate_deployment_info_docker(self.ctx)

    def initialize_driver(
        self,
        ctx,
        start_scripts: List[str] = [],
        tests: str = "",
        keep_vm_state: bool = False,
    ):
        DockerFlavour.driver = DockerDriver(ctx, start_scripts, tests, keep_vm_state)
        return DockerFlavour.driver
