import os
import os.path as op
import sys
import click

from . import VERSION
from .context import pass_context, CONTEXT_SETTINGS

click.disable_unicode_literals_warning = True


class NixosComposeCLI(click.MultiCommand):

    def list_commands(self, ctx):
        cmd_folder = op.abspath(op.join(op.dirname(__file__), 'commands'))
        commands = []
        for filename in os.listdir(cmd_folder):
            if filename.endswith('.py') and filename.startswith('cmd_'):
                commands.append(filename[4:-3])
        commands.sort()
        return commands

    def get_command(self, ctx, name):
        if name in self.list_commands(ctx):
            mod = __import__('nixos_compose.commands.cmd_' + name,
                             None, None, ['cli'])
            return mod.cli


@click.command(cls= NixosComposeCLI, context_settings=CONTEXT_SETTINGS, chain=True)
@click.option('--workdir', type=click.Path(exists=True, file_okay=False,
                                           resolve_path=True),
              help='Changes the folder to operate on.')
@click.option('--verbose', '-v', is_flag=True, default=False,
              help="Verbose mode.")
@click.option('--debug', '-d', is_flag=True, default=False,
              help="Enable debugging")
@click.version_option(version=VERSION)
@pass_context
def cli(ctx, workdir, verbose, debug):
    """Generate and manage multi Nixos composition."""
    if workdir is not None:
        ctx.workdir = workdir
    ctx.verbose = verbose
    ctx.debug = debug


def main(args=sys.argv[1:]):
    cli(args)
