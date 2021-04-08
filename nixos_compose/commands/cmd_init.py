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

FLAKE = """{
  description = "nixos-compose - composition to infrastructure";
  $input_nur
  outputs = { self, nixpkgs$nur_arg }:
    let
      system = "x86_64-linux";

      flavours = import ./nix/flavours.nix;
      $nur
    in {
      packages.$${system} = nixpkgs.lib.mapAttrs (name: flavour:
        (import ./nix/compose.nix) {
          inherit nixpkgs system$extra_configurations flavour;
        }) flavours;

      defaultPackage.$${system} = self.packages.$${system}.$default_flavour;

    };
}"""

INPUT_NUR_FLAKE = """
  inputs.NUR.url = "github:nix-community/NUR";
  #inputs.alice.url = "path:/home/some_path/nur-alice";
"""

NUR_FLAKE = """
      nur = import ./nix/nur.nix {
        inherit nixpkgs system NUR;
        # for repo override if needed
        #repoOverrides = { inherit alice; };
      };

      extraConfigurations = [
        # add nur attribute to pkgs
        { nixpkgs.overlays = [ nur.overlay ]; }
        #nur.repos.alice.modules.foo
      ];
"""

DEFAULT_COMPAT_FLAKE = """(import (builtins.fetchTarball https://github.com/edolstra/flake-compat/archive/master.tar.gz) {
  src = ./.;
}).defaultNix"""

DEFAULT = """{ nixpkgs ? <nixpkgs>, system ? builtins.currentSystem, flavour ? "$default_flavour"
}:
$nur
(import ./nix/compose.nix) {
  inherit nixpkgs system$extra_configurations flavour;
}
"""

DEFAULT_NUR = """
let
  NUR = builtins.fetchTarball
    "https://github.com/nix-community/NUR/archive/master.tar.gz";

  nur = import ./nix/nur.nix {
    inherit nixpkgs system NUR;
    # for repo override if needed
    #repoOverrides = { alice = /home/some_path/nur-alice; };
  };

  extraConfigurations = [
    # add nur attribute to pkgs
    { nixpkgs.overlays = [ nur.overlay ]; }
    # import NUR modules like this:
    #nur.repos.alice.modules.foo
  ];
in
"""


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
@click.option("--nur", is_flag=True, help="Add Nix User Repository (NUR) access.")
@click.option(
    "-f",
    "--default-flavour",
    type=click.STRING,
    help="Set default flavour to build, if not given nixos-compose try to find a good",
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
def cli(ctx, example, no_symlink, disable_detection, flake, nur, default_flavour):
    """Initialize a new environment."""

    nxc_json_file = op.abspath(op.join(ctx.envdir, "nxc.json"))

    example_path = op.abspath(op.join(EXAMPLES_PATH, example))
    if op.isdir(example_path):
        copy_tree(example_path, ctx.envdir)
        copy_tree(
            NXC_NIX_PATH, op.abspath(op.join(ctx.envdir, "nix")),
        )
    else:

        composition_file = "composition.nix"
        composition_path = op.abspath(op.join(ctx.envdir, composition_file))
        click.echo("\nCopy intial files: ")
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

        if not default_flavour:
            # determine default flavour
            if ctx.platform:
                default_flavour = ctx.platform.default_flavour
            else:
                default_flavour = "nixos-test"
        click.echo("      default flavour: " + click.style(default_flavour, fg="green"))

        nur_str = ""
        nur_arg = ""
        extra_configurations = ""
        input_nur = ""
        if nur:
            extra_configurations = " extraConfigurations"
            if flake:
                nur_str = NUR_FLAKE
                nur_arg = ", nur"
                input_nur = INPUT_NUR_FLAKE
            else:
                nur_str = DEFAULT_NUR

            click.echo("      add nur:" + click.style("done", fg="green"))

        if flake:
            click.echo("\nCreate files for flake support:")

            t = Template(FLAKE)
            flake_nix = t.substitute(
                default_flavour=default_flavour,
                nur=nur_str,
                nur_arg=nur_arg,
                input_nur=input_nur,
                extra_configurations=extra_configurations,
            )

            click.echo("   " + create + "  flake.nix")
            with open(op.abspath(op.join(ctx.envdir, "flake.nix")), "w") as f:
                f.write(flake_nix)

                click.echo("   " + create + "  default.nix")
                with open(op.abspath(op.join(ctx.envdir, "default.nix")), "w") as f:
                    f.write(DEFAULT_COMPAT_FLAKE)
        else:
            click.echo("\nCreate default file:")
            click.echo("   " + create + "  default.nix")
            t = Template(DEFAULT)
            default_nix = t.substitute(
                default_flavour=default_flavour,
                nur=nur_str,
                extra_configurations=extra_configurations,
            )
            with open(op.abspath(op.join(ctx.envdir, "default.nix")), "w") as f:
                f.write(default_nix)

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
