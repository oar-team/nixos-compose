import os
import os.path as op
import sys
import pkg_resources

import click

from .context import pass_context, CONTEXT_SETTINGS

click.disable_unicode_literals_warning = True
version = pkg_resources.get_distribution("nixos-compose").version


class NixosComposeCLI(click.MultiCommand):
    def list_commands(self, ctx):
        cmd_folder = op.abspath(op.join(op.dirname(__file__), "commands"))
        commands = []
        for filename in os.listdir(cmd_folder):
            if filename.endswith(".py") and filename.startswith("cmd_"):
                commands.append(filename[4:-3])
        commands.sort()
        return commands

    def get_command(self, ctx, name):
        if name in self.list_commands(ctx):
            mod = __import__("nixos_compose.commands.cmd_" + name, None, None, ["cli"])
            return mod.cli


@click.command(cls=NixosComposeCLI, context_settings=CONTEXT_SETTINGS, chain=True)
@click.option(
    "--envdir",
    "-d",
    type=click.Path(file_okay=False, resolve_path=True),
    default=op.abspath("./nxc"),
    help="Changes the folder to operate on.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose mode.")
@click.option("--debug", "-D", is_flag=True, default=False, help="Enable debugging")
@click.version_option(version=version)
@pass_context
def cli(ctx, envdir, verbose, debug):
    """Generate and manage multi Nixos composition."""
    ctx.envdir = envdir
    if os.path.isfile("nxc.json"):
        if os.path.islink("nxc.json"):
            ctx.nxc_file = os.readlink("nxc.json")
        else:
            ctx.nxc_file = op.abspath("nxc.json")
        with open(ctx.nxc_file, "r") as f:
            ctx.load_nxc(f)

        ctx.envdir = op.dirname(ctx.nxc_file)

    ctx.verbose = verbose
    ctx.debug = debug
    # ctx.update() not use


def main(args=sys.argv[1:]):
    cli(args)
