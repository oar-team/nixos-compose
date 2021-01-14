import os
import os.path as op
import json
import random

from io import open

import click

from ..context import pass_context, on_finished
from ..utils import copy_tree, copy_file

EXAMPLES_PATH = op.abspath(op.join(op.dirname(__file__), "../..", "examples"))
EXAMPLES = os.listdir(EXAMPLES_PATH)
NXC_NIX_PATH = op.abspath(op.join(op.dirname(__file__), "../../nix"))


@click.command("init")
# @click.option("-f", "--force", is_flag=True, help="Overwrite existing env")
@click.option(
    "-e",
    "--example",
    default="test-vm.nix",
    help="Use example",
    show_default=True,
    type=click.Choice(EXAMPLES),
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
def cli(ctx, example):
    """Initialize a new environment."""

    overwrite = False

    example_path = op.abspath(op.join(EXAMPLES_PATH, example))
    composition_path = op.abspath(op.join(ctx.envdir, example))

    create = click.style("   create", fg="green")
    click.echo("   " + create + "  " + ctx.envdir)
    os.mkdir(ctx.envdir)

    click.echo("   " + create + "  " + composition_path)
    copy_file(
        example_path, composition_path,
    )
    # composition_path2 = op.abspath(op.join(ctx.envdir, "..", "composition.nix"))
    # if composition_path != composition_path2:
    #    os.symlink(composition_path, composition_path2)

    copy_tree(
        NXC_NIX_PATH, op.abspath(op.join(ctx.envdir, "nix")),
    )
    nxc_json = {"envdir": ctx.envdir, "composition": composition_path}
    nxc_json_str = json.dumps(nxc_json)
    nxc_json_file = op.abspath(op.join(ctx.envdir, "nxc.json"))

    ctx.nxc = nxc_json
    ctx.nxc_file = nxc_json_file

    click.echo("   " + create + "  " + nxc_json_file)

    with open(nxc_json_file, "w") as f:
        f.write(nxc_json_str)
    os.symlink(nxc_json_file, op.abspath(op.join(ctx.envdir, "..", "nxc.json")))

    ctx.log(
        "Initialized nixos-compose environment in %s", click.format_filename(ctx.envdir)
    )

    # ctx.init_env(env_name=env, env_id=env_id)
