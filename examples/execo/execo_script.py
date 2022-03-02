from nixos_compose.nxc_execo import get_oar_job_nodes_nxc, build_nxc_execo

from execo import Process, SshProcess, Remote
from execo_g5k import oardel, oarsub, OarSubmission, get_oar_job_nodes
from execo_engine import Engine, logger, ParamSweeper, sweep

import sys
import os


class MyEngine(Engine):
    def __init__(self):
        super(MyEngine, self).__init__()
        parser = self.args_parser
        parser.add_argument('--nxc_build_file', help='Path to the NXC deploy file')
        parser.add_argument('--build', action='store_true', help='Either to build the composition')
        parser.add_argument('--nxc_folder', default=f"{os.getcwd()}", help='Path to the nxc folder')
        self.nodes = {}
        self.oar_job_id = -1

    def init(self):
        nb_nodes = 2
        site = "grenoble"
        cluster = "dahu"

        nxc_build_file = None
        if self.args.build:
            (nxc_build_file, _time, _size) = build_nxc_execo(self.args.nxc_folder, site, cluster, walltime=15*60, extra_job_type=["day"])
        elif self.args.nxc_build_file is not None:
            nxc_build_file = self.args.nxc_build_file
        else:
            raise Exception("No compose info file ...")

        print(nxc_build_file)
        oar_job = reserve_nodes(nb_nodes, site, cluster, walltime=15*60)
        self.oar_job_id, site = oar_job[0]
        roles_quantities = {"foo": ["foo", "bar"]}
        self.nodes = get_oar_job_nodes_nxc(self.oar_job_id, site, compose_info_file=nxc_build_file, roles_quantities=roles_quantities)
        print(self.nodes)

    def run(self):
        my_command = "echo \"Hello from $(whoami) at $(hostname) ($(ip -4 addr | grep \"/20\" | awk '{print $2;}'))\" > /tmp/hello"
        hello_remote = Remote(my_command, self.nodes["foo"], connection_params={'user': 'root'})
        hello_remote.run()

        my_command2 = "cat /tmp/hello"
        cat_remote = Remote(my_command2, self.nodes["foo"], connection_params={'user': 'root'})
        cat_remote.run()
        for process in cat_remote.processes:
            print(process.stdout)

def reserve_nodes(nb_nodes, site, cluster, walltime=3600):
    jobs = oarsub([(OarSubmission("{{cluster='{}'}}/nodes={}".format(cluster, nb_nodes), walltime, job_type=["allow_classic_ssh", "day"]), site)])
    return jobs

if __name__ == "__main__":
    ENGINE = MyEngine()
    try:
        ENGINE.start()
    except Exception as ex:
        print(f"Failing with error {ex}")
        oardel([(ENGINE.oar_job_id, None)])
        print("Giving back the resources")
