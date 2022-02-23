import os
import os.path as op
import json
import subprocess
import click

from ..flavour import Flavour
from ..actions import read_compose_info
from ..driver.logger import rootlog
from ..driver.machine import Machine

from typing import List, Tuple, Optional

def generate_docker_compose_file(ctx, roles_quantities={}):
    base_docker_compose = ctx.compose_info["docker-compose-file"]
    docker_compose_content = {"services": {}}
    with open(base_docker_compose) as dc_file:
        dc_json = json.load(dc_file)
        if roles_quantities == {}:
            roles_quantities = {role: 1 for role in ctx.compose_info["nodes"]}
        for role, quantities in roles_quantities.items():
            if type(quantities) is int:
                for i in range(1, quantities + 1):
                    hostname = f"{role}{i}"
                    config = dc_json["services"][role]
                    config["hostname"] = hostname
                    docker_compose_content["services"][hostname] = config
            elif type(quantities) is list:
                for hostname in quantities:
                    config = dc_json["services"][role]
                    config["hostname"] = hostname
                    docker_compose_content["services"][hostname] = config
            else:
                raise Exception("Unvalid type for specifying the roles of the nodes")
        docker_compose_content["version"] = dc_json["version"]
        docker_compose_content["x-nxc"] = dc_json["x-nxc"]

    deploy_dir = op.join(ctx.envdir, "deploy", "docker_compose")
    if not op.exists(deploy_dir):
        create = click.style("   create", fg="green")
        ctx.log("   " + create + "  " + deploy_dir)
        os.mkdir(deploy_dir)
    docker_compose_path = op.join(deploy_dir, "docker-compose.json")

    with open(
        docker_compose_path, "w"
    ) as outfile:
        outfile.write(json.dumps(docker_compose_content))
    return docker_compose_path


def generate_deployment_info_docker(ctx):
    if not ctx.compose_info:
        read_compose_info(ctx)

    docker_compose_path = generate_docker_compose_file(ctx)#, {"foo": 2})
    deployment = {
        "nodes": ctx.compose_info["nodes"],
        "deployment": {n: {"role": n} for n in ctx.compose_info["nodes"]},
        "docker-compose-file": docker_compose_path
    }

    if "all" in ctx.compose_info:
        deployment["all"] = ctx.compose_info["all"]

    json_deployment = json.dumps(deployment, indent=2)

    deploy_dir = op.join(ctx.envdir, "deploy")
    if not op.exists(deploy_dir):
        create = click.style("   create", fg="green")
        ctx.log("   " + create + "  " + deploy_dir)
        os.mkdir(deploy_dir)

    with open(
        op.join(deploy_dir, f"{ctx.composition_flavour_prefix}.json"), "w"
    ) as outfile:
        outfile.write(json_deployment)

    ctx.deployment_info = deployment
    return


class DockerFlavour(Flavour):

    docker_compose_file = None
    machines: List[Machine] = []

    started_all = False

    def __init__(self, ctx):
        super().__init__(ctx)

        self.name = "docker"
        self.description = ""
        self.docker_processes = {}

    def generate_deployment_info(self):
        generate_deployment_info_docker(self.ctx)
        # berk
        self.ctx.compose_info["docker-compose-file"] = op.join(self.ctx.envdir, "deploy", "docker_compose", "docker-compose.json")
        self.docker_compose_file = self.ctx.compose_info["docker-compose-file"]

    def driver_initialize(self, tmp_dir):
        nodes_names = self.ctx.compose_info["nodes"]
        for name in nodes_names:
            self.machines.append(
                Machine(self.ctx, tmp_dir=tmp_dir, start_command="", name=name,)
            )

    def check(self, state="running"):
        check_process = subprocess.check_output(
            [
                "docker-compose",
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
        with rootlog.nested("starting docker-compose"):
            subprocess.Popen(
                ["docker-compose", "-f", self.docker_compose_file, "up", "-d"]
            )

        self.wait_on_check()

        for machine in self.machines:
            self.start(machine)
            self.connected = True

    def start(self, machine):
        assert machine.name
        assert self.docker_compose_file

        self.docker_processes[machine] = subprocess.Popen(
            [
                "docker-compose",
                "-f",
                self.docker_compose_file,
                "exec",
                "-T",
                machine.name,
                "bash",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def execute(
        self,
        machine,
        command: str,
        check_return: bool = True,
        timeout: Optional[int] = 900,
    ) -> Tuple[int, str]:

        self.connect(machine)

        docker_process = self.docker_processes[machine]
        try:
            (stdout, _stderr) = docker_process.communicate(
                command.encode(), timeout=timeout
            )
        except subprocess.TimeoutExpired:
            docker_process.kill()
            return (-1, "")
        status_code = docker_process.returncode
        self.restart(machine)
        return (status_code, stdout.decode())

    def restart(self, machine):
        if machine in self.docker_processes and self.docker_processes[machine]:
            self.docker_processes[machine]
        self.start(machine)

    def cleanup(self):
        # TODO handle stdout/stderr
        if not self.docker_compose_file:
            self.docker_compose_file = self.ctx.deployment_info["docker-compose-file"]
        subprocess.Popen(
            [
                "docker-compose",
                "-f",
                self.docker_compose_file,
                "down",
                "--remove-orphans",
            ]
        )

    def shell_interact(self, machine) -> None:
        self.connect(machine)
        print("not yet implemented")

    def ext_connect(self, user, node, execute=True):
        if not self.docker_compose_file:
            self.docker_compose_file = self.ctx.deployment_info["docker-compose-file"]

        cmd = f"docker-compose -f {self.docker_compose_file} exec -u {user} {node} /bin/sh -c bash"

        if execute:
            return_code = subprocess.run(cmd, shell=True).returncode

            if return_code:
                self.ctx.wlog(f"Docker exit code is not null: {return_code}")
            return return_code
        else:
            return cmd
