import click
import os
import os.path as op
import glob

from ..context import pass_context
from ..actions import read_deployment_info
from ..flavours import get_flavour_by_name


@click.command("stop")
@click.option(
    "-f", "--flavour", type=click.STRING, help="specify flavour",
)
@click.option(
    "-d", "--deployment-file", type=click.STRING, help="specify deployment",
)
@pass_context
def cli(ctx, flavour, deployment_file):
    """Stop Nixos composition."""
    ctx.log("Stopping")

    flavour_name = flavour

    deploy_path = op.join(ctx.envdir, "deploy")

    if not deployment_file:
        if flavour_name:
            search_path = f"{deploy_path}/*::{flavour_name}.json"
        else:
            search_path = f"{deploy_path}/*"

        deploy_paths = glob.glob(search_path)
        if not deploy_paths:
            raise click.ClickException("Failed to find last deployment file")

        last_deploy_path = max(
            deploy_paths, key=lambda x: os.stat(x, follow_symlinks=False).st_ctime,
        )

        deployment_file = last_deploy_path
        ctx.log("Use last deployment file:")
        ctx.glog(last_deploy_path)

        # ctx.composition_flavour_prefix = op.basename(last_deploy_path)

    splitted_filename = deployment_file.split("::")

    if len(splitted_filename) != 2:
        raise click.ClickException("Sorry, filename is malformed")

    splitted_last = splitted_filename[-1].split(".")
    if splitted_last[-1] != "json":
        raise click.ClickException("Sorry, filename is malformed")

    if flavour_name:
        assert flavour_name == splitted_last[0]
    else:
        flavour_name = splitted_last[0]

    ctx.flavour = get_flavour_by_name(flavour_name)(ctx)

    read_deployment_info(ctx, deployment_file)

    ctx.flavour.cleanup()
