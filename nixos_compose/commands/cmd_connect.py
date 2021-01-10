import click
from ..context import pass_context  # , on_started, on_finished
from ..actions import connect


@click.command("connect")
@click.option("-l", "--user", default="root")
@click.argument("hostname")
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, hostname):
    """Connect to a machine."""
    connect(ctx, user, hostname)
