import os
import os.path as op
import click
import shutil

from ..context import pass_context, on_finished

NXC_FOLDER_PATH = op.abspath(op.join(op.dirname(__file__), "../../nxc"))
NXC_JSON_PATH = op.abspath(op.join(op.dirname(__file__), "../../nxc.json"))


@click.command("clean")
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
def cli(ctx):
    """Clean the nxc folder and nxc.json file"""
    if os.path.isfile(NXC_JSON_PATH):
        os.remove(NXC_JSON_PATH)

    if os.path.isdir(NXC_FOLDER_PATH):
        shutil.rmtree(NXC_FOLDER_PATH)
