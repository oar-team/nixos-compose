#!/usr/bin/env python
from execo import Remote
from execo_engine import Engine, logger
from execo_g5k import (
    OarSubmission,
    oardel,
    oarsub,
    wait_oar_job_start,
)
from nixos_compose.nxc_execo import get_oar_job_nodes_nxc


class MyEngine(Engine):
    def __init__(self):
        super(MyEngine, self).__init__()
        self.oar_job_id = None
        parser = self.args_parser
        parser.add_argument("--nxc_build_file", help="Path to the NXC build file")
        parser.add_argument("--walltime", help="Grid5000 booking walltime (in hours)")
        parser.add_argument(
            "--flavour", help="Nixos compose flavour", default="g5k-image"
        )
        parser.add_argument(
            "--keep-job",
            help="Do not delete the OAR job after execution, be it after an error or success",
            action="store_true",
        )
        parser.add_argument(
            "--job-id",
            help="When provided, the given OAR job ID is used and no further booking is done",
            type=int,
        )

    def init(self):
        pass

    def run(self):
        # Initialise some experiment parameters
        site = "grenoble"
        cluster = "dahu"
        nxc_flavour = self.args.flavour
        nb_nodes = 2
        roles_distribution = {
            "foo": ["foo", "bar"],
        }
        walltime_hours = float(self.args.walltime) if self.args.walltime else 1
        # Local copies of experiment parameters

        try:
            # Book nodes on Grid 5000 unless the ID of an existing job has been provided
            if self.args.job_id is None:
                # Book nodes on Grid'5000
                logger.info(f"Reserving {nb_nodes} node.s on {site}-{cluster}...")
                oar_job = reserve_nodes(
                    nb_nodes, site, cluster, "deploy", walltime=walltime_hours * 60 * 60
                )
                self.oar_job_id, site = oar_job[0]

                logger.info(f"Waiting for job ID {self.oar_job_id} on {site} site...")
                wait_oar_job_start(self.oar_job_id, site)
            else:
                self.oar_job_id = self.args.job_id

            # Get the machines info, deploy
            logger.info("Deploying ...")
            nodes, roles = get_oar_job_nodes_nxc(
                self.oar_job_id,
                site,
                flavour_name=nxc_flavour,
                compose_info_file=self.args.nxc_build_file,
                # composition_name = "", # for multiple compositions case
                roles_quantities=roles_distribution,
            )
            logger.info(f"... done. Nodes used for this experiment: {nodes}")

            #
            logger.debug("Execute on hello")

            my_command = 'echo "Hello from $(whoami) at $(hostname) ($(ip -4 addr | grep "/20" | awk \'{print $2;}\'))" > /tmp/hello'
            hello_remote = Remote(
                my_command, nodes["foo"], connection_params={"user": "root"}
            )
            hello_remote.run()
            # throw_on_problem( hello_remote)

            my_command2 = "cat /tmp/hello"
            cat_remote = Remote(
                my_command2, nodes["foo"], connection_params={"user": "root"}
            )
            cat_remote.run()
            for process in cat_remote.processes:
                print(process.stdout)
        except FailedProcessError as e:
            logger.error(f"Failed at process {e}")
        except KeyboardInterrupt:
            logger.info("Stopping (received keyboard interrupt)")
        finally:
            if self.oar_job_id is not None and not self.args.keep_job:
                logger.info(f"Giving back the resources (OAR job ID {self.oar_job_id})")
                oardel([(self.oar_job_id, "site")])


class FailedProcessError(Exception):
    """Exception raised when an Execo process failed (meaning its attribute finished_ok is False)"""

    def __init__(self, process):
        super(Exception, self).__init__()
        self.process = process

    def __str__(self):
        return str(self.process)


def throw_on_problem(process):
    """Raise if the given process did not finish properly (meaning attribute finished_ok is False)"""
    if not process.finished_ok:
        raise FailedProcessError(process)


def reserve_nodes(nb_nodes, site, cluster, job_type, walltime=3600):
    """
    :param walltime: the duration of the job, in seconds (or a datetime, or a string as expected by the oarsub program)
    """
    jobs = oarsub(
        [
            (
                OarSubmission(
                    resources="{{cluster='{}'}}/nodes={}".format(cluster, nb_nodes),
                    walltime=walltime,
                    job_type=[job_type],
                ),
                # additional_options = '-t exotic'),
                site,
            )
        ]
    )
    return jobs


if __name__ == "__main__":
    ENGINE = MyEngine()
    try:
        ENGINE.start()
    except Exception as ex:
        print(f"Failing with error {ex}")
        oardel([(ENGINE.oar_job_id, None)])
        print("Giving back the resources")
