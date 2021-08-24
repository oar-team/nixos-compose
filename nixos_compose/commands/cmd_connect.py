import sys
import click
from ..context import pass_context  # , on_started, on_finished
from ..actions import read_deployment_info, connect, connect_tmux, connect_docker


@click.command("connect")
@click.option("-l", "--user", default="root")
@click.option(
    "-g",
    "--geometry",
    help='Tmux geometry, 2 splitting indications are supported: +/*, examples: "1+3+2" (3 sucessive panes respectively horizontally splited by 1,3 and 2), "2*3" (2 sucessive panes horizontally splitted by 3)',
)
@click.option(
    "-d",
    "--deployment-file",
    help="Deployment file, take the latest created in deploy directory by default",
)
@click.option(
    "-nc", "--no-pane-console", is_flag=True, help="Remove addtional pane console"
)
@click.argument("host", nargs=-1)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, host, geometry, no_pane_console, deployment_file):
    """Connect to host."""
    read_deployment_info(ctx, deployment_file)

    if not host or len(host) > 1:
        # TODO  add wait_ssh
        if ctx.deployment_info["docker-compose-file"]:
            ctx.elog(
                "Not yet implemented for Docker flavour, you must indicate only ONE host"
            )
            sys.exit(1)
        # TODO  add wait_ssh
        connect_tmux(ctx, user, host, no_pane_console, geometry, "nxc")
    else:
        if ctx.deployment_info["docker-compose-file"]:
            connect_docker(ctx, user, host[0])
        else:
            connect(ctx, user, host[0])
