import click
import re
from ..context import pass_context  # , on_started, on_finished
from ..actions import read_deployment_info, connect_tmux
from ..flavours import get_flavour_by_name


@click.command("connect")
@click.option("-l", "--user", default="root")
@click.option(
    "-g",
    "--geometry",
    help='Tmux geometry, 2 splitting indications are supported: +/*, examples: "1+3+2" (3 adjacent panes respectively horizontally splited by 1,3 and 2), "2*3" (2 adjacent panes horizontally splitted by 3)',
)
@click.option(
    "-d",
    "--deployment-file",
    help="Deployment file, take the latest created in deploy directory by default",
)
@click.option(
    "-f",
    "--flavour",
    help="flavour, by default it's extracted from deployment file name",
)
@click.option(
    "-i",
    "--identity-file",
    type=click.STRING,
    help="path to the ssh public private used to connect to the deployments",
)
@click.option(
    "-a",
    "--tag",
    help="tagname of the deployment we want to connect on",
)
@click.option("-pc", "--pane-console", is_flag=True, help="Add a pane console")
@click.argument("host", nargs=-1)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(
    ctx, user, host, geometry, pane_console, deployment_file, flavour, identity_file, tag
):
    """
    Opens one or more terminal sessions into the deployed nodes. By default, it will connect to all nodes, but we can specify which ones to connect to.

    To connect to several machines at once `nxc` use a tmux (terminal multiplexer) session. Feel free to refer to the [tmux documentation](https://github.com/tmux/tmux/wiki) (or its [cheatsheet](https://tmuxcheatsheet.com/)), especially for the shortcuts to navigate between the different tabs.

    ## Examples

    - `nxc connect`

        Open a Tmux session with one panel for each node.

    - `nxc connect server`

        Connect to the `server` node. It runs on the current shell (Tmux is not used in this case)
    """
    read_deployment_info(ctx, deployment_file, flavour, tag)

    # determine flavour name
    if not flavour:
        match = re.match(r"^.*?::([^:]+?)(?:::|\.).*$", ctx.deployment_filename)
        if match:
            flavour = match.group(1)
        else:
            raise click.ClickException(
                "Cannot determined flavour, one must by provided (option fix deployment file name or use --flavour option"
            )

    ctx.flavour = get_flavour_by_name(flavour)(ctx)

    if not host or len(host) > 1:
        # TODO  add wait_ssh
        connect_tmux(ctx, user, host, identity_file, pane_console, geometry, "nxc")
    else:
        ctx.flavour.ext_connect(user, host[0], ssh_key_file=identity_file)

        # if "docker-compose-file" in ctx.deployment_info:
        #    connect_docker(ctx, user, host[0])
        # else:
        #    connect(ctx, user, host[0])
