import click
from ..context import pass_context  # , on_started, on_finished
from ..actions import read_deployment_info, connect, connect_tmux


@click.command("connect")
@click.option("-l", "--user", default="root")
@click.option(
    "-g",
    "--geometry",
    help='Define tmux geometry, 2 formats supported: +/*, examples: "1+3+2" (3 sucessive panes respectively horizontally splitted by 1,3 and 2), "2*3" (2 sucessive panes horizontally splitted by 3)',
)
@click.option(
    "-nc", "--no-pane-console", is_flag=True, help="Remove addtional pane console"
)
@click.argument("host", nargs=-1)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, host, geometry, no_pane_console):
    """Connect to host."""
    read_deployment_info(ctx, deployment_file="deployment.json")

    if not host or len(host) > 1:
        # TODO  add wait_ssh
        connect_tmux(ctx, user, host, no_pane_console, geometry, "nxc")
    else:
        connect(ctx, user, host[0])
