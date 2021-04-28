import os
import socket
import click
import subprocess
import json
import time
from halo import Halo


class Platform(object):
    def __init__(self, ctx, name):  # TODO ctx remove ?
        self.name = name
        ctx.state["platform"] = name  # TODO remove ?
        self.copy_from_store = False

    def retrieve_machines(self, ctx):
        pass

    def get_start_values(self, ctx):
        pass


class Grid5000Platform(Platform):
    def __init__(self, ctx):
        super().__init__(ctx, "Grid5000")
        self.default_flavour = "g5k-ramdisk"
        self.copy_from_store = True
        self.first_start_values = ("oarsh", "sudo-g5k", None)
        self.subsequent_start_values = ("ssh", "sudo", "/")
        self.oar_job_id = None
        self.oar_job = None

    def retrieve_machines(self, ctx):

        oar_job = None
        oar_job_id_str = None
        oar_job_id_prev_str = None
        halo = False

        if "oar_job_id" in ctx.state:
            oar_job_id_prev_str = str(ctx.state["oar_job_id"])

        def oarstat():
            output = subprocess.check_output("oarstat -u -J", shell=True)
            ctx.vlog(output)
            return json.loads(output)

        o = oarstat()
        if "OAR_JOB_ID" in os.environ:
            oar_job_id_str = os.environ["OAR_JOB_ID"]
        elif (
            oar_job_id_prev_str
            and oar_job_id_prev_str in o
            and o[oar_job_id_prev_str]["state"] == "Running"
        ):
            oar_job_id_str = str(ctx.state["oar_job_id"])
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
        # TODO test when job exist but not Running or Launching (other states not supported)
        if oar_job_id_str in o.keys():
            oar_job = o[oar_job_id_str]

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

        if "oar_job_id" not in ctx.state:
            ctx.state["oar_job_id"] = self.oar_job_id

        return oar_job["assigned_network_address"]

    def get_start_values(self, ctx):
        assert "oar_job_id" in ctx.state
        if ctx.state["started"]:
            return self.subsequent_start_values
        else:
            os.environ["OAR_JOB_ID"] = str(self.oar_job_id)
            return self.first_start_values


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
        ctx.state["platform"] = ctx.platform.name
    else:
        click.echo("      no particular platform detected, local mode will be used")
    return
