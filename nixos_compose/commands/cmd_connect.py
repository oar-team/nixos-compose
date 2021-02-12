import click
from ..context import pass_context  # , on_started, on_finished
from ..actions import read_deployment_info, connect, connect_tmux


@click.command("connect")
@click.option("-l", "--user", default="root")
@click.argument("host", required=False)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, host):
    """Connect to host."""
    read_deployment_info(ctx, deployment_file="deployment.json")
    if not host:
        # add wait_ssh
        connect_tmux(ctx, user, host)
    else:
        connect(ctx, user, host)
