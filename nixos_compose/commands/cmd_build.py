import click

from ..context import pass_context, on_started, on_finished 
from ..actions import read_compose_info, copy_result_from_store
import time
import sys
import subprocess


@click.command("build")
@click.argument("composition_file", required=False, type=click.STRING)
@click.option(
    "--nix-path",
    "-I",
    multiple=True,
    help="add a path to the list of locations used to look up <...> file names",
)
@click.option(
    "--out-link", "-o", default="result", help="path of the symlink to the build result"
)
@click.option("--nixpkgs", "-n", default="channel:nixos-20.09")
@click.option("--nixos-test", is_flag=True, help="generate NixOS Test driver")
@click.option(
    "--copy-from-store", "-c", is_flag=True, help="copy artifact from Nix store"
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(
    ctx, composition_file, nix_path, out_link, nixpkgs, nixos_test, copy_from_store
):
    """Build multi Nixos composition.
    Typically it performs the kind of following command:
      nix build -f examples/webserver-flavour.nix -I compose=nix/compose.nix -I nixpkgs=channel:nixos-20.09 -o result-local
    """
    ctx.log("Starting build")

    if not composition_file:
        composition_file = ctx.nxc['composition']

    build_cmd = f"nix build -f {composition_file} -I  compose=nix/compose.nix"
    build_cmd += f" -I nixpkgs={nixpkgs} -o {out_link}"
    if nixos_test:
        build_cmd += " driver"

    ctx.vlog(build_cmd)
    subprocess.call(build_cmd, shell=True)

    if copy_from_store:
        copy_result_from_store(".", read_compose_info())

    ctx.glog("Build completed")
