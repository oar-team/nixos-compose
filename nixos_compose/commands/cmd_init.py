import os
import os.path as op
import json
from string import Template

from io import open

import click

from ..context import pass_context, on_finished
from ..platform import platform_detection
from ..utils import copy_tree, copy_file

EXAMPLES_PATH = op.abspath(op.join(op.dirname(__file__), "../..", "examples"))
EXAMPLES = os.listdir(EXAMPLES_PATH)
NXC_NIX_PATH = op.abspath(op.join(op.dirname(__file__), "../../nix"))

FLAKE_TEMPLATE = """{
  description = "nixos-compose - composition to infrastructure";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";

      composition = import ./$composition;

      nixos_test = import ./nix/nixos-test.nix;
      generate = import ./nix/generate.nix;
      flavours = import ./nix/flavours.nix;

    in {
      packages.x86_64-linux = nixpkgs.lib.mapAttrs (name: flavour:
        generate { inherit nixpkgs system flavour; } composition) flavours // {
          nixos-test = nixos_test { inherit nixpkgs system; } composition;
          nixos-test-driver =
            (nixos_test { inherit nixpkgs system; } composition).driver;
        };
      defaultPackage.x86_64-linux = self.packages.x86_64-linux.$default_flavour;
    };
}"""

DEFAULT_COMPAT_FLAKE = """(import (builtins.fetchTarball https://github.com/edolstra/flake-compat/archive/master.tar.gz) {
  src = ./.;
}).defaultNix"""


@click.command("init")
# @click.option("-f", "--force", is_flag=True, help="Overwrite existing env")
@click.option(
    "-e",
    "--example",
    default="composition.nix",
    help="Use example",
    show_default=True,
    type=click.Choice(EXAMPLES),
)
@click.option(
    "--no-symlink",
    is_flag=True,
    help="Disable symlink creation to nxc.json (need to change directory for next command",
)
@click.option(
    "-n", "--disable-detection", is_flag=True, help="Disable platform detection."
)
@click.option(
    "--flake", is_flag=True, help="Add flake.nix and default.nix for compatibility."
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
def cli(ctx, example, no_symlink, disable_detection, flake):
    """Initialize a new environment."""

    nxc_json_file = op.abspath(op.join(ctx.envdir, "nxc.json"))

    example_path = op.abspath(op.join(EXAMPLES_PATH, example))
    if op.isdir(example_path):
        copy_tree(example_path, ctx.envdir)

    else:

        composition_file = example
        composition_path = op.abspath(op.join(ctx.envdir, composition_file))

        create = click.style("   create", fg="green")
        click.echo("   " + create + "  " + ctx.envdir)
        os.mkdir(ctx.envdir)

        click.echo("   " + create + "  " + composition_path)
        copy_file(
            example_path, composition_path,
        )

        copy_tree(
            NXC_NIX_PATH, op.abspath(op.join(ctx.envdir, "nix")),
        )

        if not disable_detection:
            platform_detection(ctx)

        if flake:
            click.echo("\nCreate files for flake support")
            # determine default flavour
            if ctx.platform:
                default_flavour = ctx.platform.default_flavour
            else:
                default_flavour = "nixos-test"

            click.echo(
                "      default flavour: " + click.style(default_flavour, fg="green")
            )

            t = Template(FLAKE_TEMPLATE)
            flake_nix = t.substitute(
                composition=composition_file, default_flavour=default_flavour
            )

            click.echo("   " + create + "  flake.nix")
            with open(op.abspath(op.join(ctx.envdir, "flake.nix")), "w") as f:
                f.write(flake_nix)

                click.echo("   " + create + "  default.nix")
                with open(op.abspath(op.join(ctx.envdir, "default.nix")), "w") as f:
                    f.write(DEFAULT_COMPAT_FLAKE)

        nxc_json = {"composition": composition_file, "flake": flake}
        nxc_json_str = json.dumps(nxc_json)

        ctx.nxc = nxc_json
        ctx.nxc_file = nxc_json_file

        click.echo("   " + create + "  " + nxc_json_file)

        with open(nxc_json_file, "w") as f:
            f.write(nxc_json_str)

    if not no_symlink:
        os.symlink(nxc_json_file, op.abspath(op.join(ctx.envdir, "..", "nxc.json")))

    ctx.log(
        "\nInitialized nixos-compose environment in "
        + click.style(click.format_filename(ctx.envdir), fg="green")
        + "\n"
    )
