import os
import socket
import click
import subprocess
import json
import time
from halo import Halo
from .actions import nix_store_location


class Platform(object):
    def __init__(self, ctx, name):
        self.name = name
        self.copy_from_store = False

    def retrieve_machines(self, ctx):
        pass

    # def get_start_values(self, ctx):
    #    pass


class Grid5000Platform(Platform):
    def __init__(self, ctx):
        super().__init__(ctx, "Grid5000")
        self.default_flavour = "g5k-nfs-store"
        self.copy_from_store = True
        self.first_start_values = ("ssh -l root", "sudo", None)
        self.subsequent_start_values = ("ssh -l root", "sudo", "/")
        self.oar_job_id = None
        self.oar_job = None
        self.group_users = "g5k-users"
        self.nix_store = nix_store_location(ctx)

    def retrieve_machines(self, ctx):

        oar_job = None
        oar_job_id_str = None
        # oar_job_id_prev_str = None
        halo = False

        # if "oar_job_id" in ctx.state:
        #    oar_job_id_prev_str = str(ctx.state["oar_job_id"])

        def oarstat():
            output = subprocess.check_output("oarstat -u -J", shell=True)
            if not output:
                raise click.ClickException(
                    click.style("Not oar job is present for this user", fg="red")
                )
            ctx.vlog(output)
            return json.loads(output)

        o = oarstat()
        if "OAR_JOB_ID" in os.environ:
            oar_job_id_str = os.environ["OAR_JOB_ID"]
        else:
            # we get the last one
            oar_job_ids = [int(jid) for jid in o.keys()]
            oar_job_ids.sort()
            if oar_job_ids:
                oar_job_id_str = str(oar_job_ids[-1])

        if not oar_job_id_str:
            raise click.ClickException(
                click.style("Unable to find a OAR_JOB_ID candidate", fg="red")
            )

        ctx.log(f"target OAR_JOB_ID={oar_job_id_str}")

        # TODO test when job exist but not Running or Launching (other states not supported)
        if oar_job_id_str in o.keys():
            oar_job = o[oar_job_id_str]
            if oar_job["state"] not in ["Running", "Launching", "Waiting"]:
                raise click.ClickException(
                    click.style(
                        f"fail to acquire OAR job {oar_job_id_str} in state: {oar_job['state']}",
                        fg="red",
                    )
                )

        if oar_job["state"] != "Running":
            spinner = Halo(text=f"Waiting OAR job: {oar_job['Job_Id']}", spinner="dots")
            halo = True
            spinner.start()

        while not oar_job or oar_job["state"] != "Running":
            time.sleep(0.25)
            o = oarstat()
            if oar_job_id_str in o.keys():
                oar_job = o[oar_job_id_str]

        if halo:
            spinner.succeed("OAR job: {oar_job['Job_Id']} id running")

        self.oar_job_id = int(oar_job_id_str)
        self.oar_job = oar_job

        # for oarsh but alter env
        os.environ["OAR_JOB_ID"] = oar_job_id_str

        return oar_job["assigned_network_address"]


# class LocalPlatform(Platform):
#     def __init__(self):
#         Platform.__init__(self, 'local')


def platform_detection(ctx):
    click.echo("\nPlatform detection:")
    split_hostname = socket.gethostbyaddr(socket.gethostname())[0].split(".")
    if len(split_hostname) >= 3 and split_hostname[2] == "grid5000":
        plt = click.style("   Grid'5000", fg="green")
        click.echo("   " + plt + " detected")
        ctx.platform = Grid5000Platform(ctx)
    else:
        click.echo("      no particular platform detected, local mode will be used")
    return
