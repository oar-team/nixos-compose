import os
import os.path as op
import sys
import subprocess
import click
import json

from ..context import pass_context, on_started, on_finished
from ..actions import copy_result_from_store

# FLAVOURS_PATH = op.abspath(op.join(op.dirname(__file__), "../", "flavours"))
# FLAVOURS = os.listdir(FLAVOURS_PATH)


@click.command("build")
@click.argument(
    "composition_file", required=False, type=click.Path(exists=True, resolve_path=True)
)
@click.option(
    "--nix-path",
    "-I",
    multiple=True,
    help="add a path to the list of locations used to look up <...> file names",
)
@click.option("--out-link", "-o", help="path of the symlink to the build result")
@click.option("--nixpkgs", "-n", help="set <nixpkgs> ex: channel:nixos-20.09")
@click.option(
    "-f", "--flavour", help="Use particular flavour (name or path)",
)
@click.option(
    "-F", "--list-flavours", is_flag=True, help="List available flavour",
)
@click.option(
    "--copy-from-store",
    "-c",
    is_flag=True,
    help="Copy artifacts (initrd, kernels, ...) from Nix store to artifact directory",
)
@click.option(
    "--legacy-nix", "-l", is_flag=True, help="Use legacy Nix's CLI.",
)
@click.option("--show-trace", is_flag=True, help="Show Nix trace")
@click.option(
    "--dry-run", is_flag=True, help="Show what this command would do without doing it"
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
@on_finished(lambda ctx: ctx.show_elapsed_time())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(
    ctx,
    composition_file,
    nix_path,
    out_link,
    nixpkgs,
    flavour,
    list_flavours,
    copy_from_store,
    legacy_nix,
    show_trace,
    dry_run,
):
    """Build multi Nixos composition.
    Typically it performs the kind of following command:
      nix build -f examples/webserver-flavour.nix -I compose=nix/compose.nix -I nixpkgs=channel:nixos-20.09 -o result-local
    """

    description_flavours_file = op.abspath(op.join(ctx.envdir, "nix/flavours.json"))
    description_flavours = json.load(open(description_flavours_file, "r"))

    flavours = [k for k in description_flavours.keys()]

    if list_flavours:
        ctx.log("Flavours List:")
        for k in flavours:
            click.echo(f"{k: <18}: {description_flavours[k]['description']}")
        sys.exit(0)

    # Do we are in flake context
    flake = True if op.exists(op.join(ctx.envdir, "flake.nix")) else False

    if not flavour and not flake:
        if ctx.platform:
            flavour = ctx.platform.default_flavour
            click.echo(
                f"Platform's default flavour setting: {click.style(flavour, fg='green')}"
            )
        else:
            flavour = "nixos-test"

    # import pdb; pdb.set_trace()
    flavour_arg = ""
    if flavour:
        if flavour not in flavours and not op.isfile(flavour):
            raise click.ClickException(
                f'"{flavour}" is neither a supported flavour nor flavour_path'
            )
        else:
            if flavour in flavours:
                flavour_arg = f" --argstr flavour {flavour}"
            else:
                flavour_arg = f" --arg flavour {op.abspath(flavour)}"

    if not composition_file:
        composition_file = ctx.nxc["composition"]

    # TODO remove, we'll use default.nix
    # compose_file = op.join(ctx.envdir, "nix/compose.nix")

    # if out_link == "result":
    #    out_link = op.join(ctx.envdir, out_link)

    nix_flake_support = False
    if not subprocess.call(
        "nix flake --help",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    ):
        nix_flake_support = True

    if legacy_nix:
        build_cmd = "nix-build"
    else:
        build_cmd = "nix build"

    if show_trace:
        build_cmd += " --show-trace"

    if nixpkgs:
        build_cmd += f" -I nixpkgs={nixpkgs}"

    if flavour_arg and not flake:
        build_cmd += f" {flavour_arg}"

    #
    if not out_link:
        build_path = op.join(ctx.envdir, "build")
        if not op.exists(build_path):
            create = click.style("   create", fg="green")
            ctx.log("   " + create + "  " + build_path)
            os.mkdir(build_path)

        if not flavour:
            if "default_flavour" in ctx.nxc:
                flavour = ctx.nxc["default_flavour"]
            else:
                flavour = "default"

        composition_name = (os.path.basename(composition_file)).split(".")[0]
        ctx.composition_name = composition_name
        ctx.flavour_name = flavour
        ctx.composition_flavour_prefix = f"{composition_name}::{flavour}"
        out_link = op.join(build_path, ctx.composition_flavour_prefix)

    build_cmd += f" -o {out_link}"

    if flake:
        if flavour:
            if nix_flake_support and not legacy_nix:
                build_cmd += f' ".#packages.x86_64-linux.{flavour}"'
            else:
                build_cmd += f" -A packages.x86_64-linux.{flavour}"
    # else:
    # TODO remove legacy_nix and use default.nix -> build_cmd += "-I composition={composition_file}"
    #    if not legacy_nix:
    # build_cmd += " -f"
    # build_cmd += f" {compose_file} -I composition={composition_file}"

    if not dry_run:
        ctx.glog("Starting Build")
        ctx.vlog(build_cmd)
        subprocess.call(build_cmd, cwd=ctx.envdir, shell=True)

        if copy_from_store or (ctx.platform and ctx.platform.copy_from_store):
            ctx.compose_info_file = op.join(build_path, ctx.composition_flavour_prefix)
            copy_result_from_store(ctx)

        ctx.state["built"] = True
        ctx.glog("Build completed")
    else:
        ctx.log("Dry-run:")
        ctx.log(f"   working directory:          {ctx.envdir}")
        ctx.log(f"   composition flavour prefix: {ctx.composition_flavour_prefix}")
        ctx.log(f"   build command:              {build_cmd}")
