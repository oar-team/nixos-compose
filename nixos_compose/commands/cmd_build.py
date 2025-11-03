import os
import os.path as op
import shutil
import sys
import subprocess
import click
import json

from ..actions import (
    get_nix_command,
    realpath_from_store,
    artifact_copy_all_kernel_initrd,
)
from ..context import pass_context, on_started, on_finished
from ..platform import platform_detection
from ..setup import apply_setup
from ..flavour import base_flavours

# FLAVOURS_PATH = op.abspath(op.join(op.dirname(__file__), "../", "flavours"))
# FLAVOURS = os.listdir(FLAVOURS_PATH)


@click.command("build")
@click.argument(
    "composition_file", required=False, type=click.Path(exists=True, resolve_path=True)
)
@click.option(
    "--nix-flags",
    type=click.STRING,
    help='add nix flags (aka options) to nix build command, --nix-flags "--impure"',
)
@click.option("--out-link", "-o", help="path of the symlink to the build result")
@click.option(
    "-f",
    "--flavour",
    type=click.STRING,
    help="Use particular flavour (name or path)",
)
@click.option(
    "-F",
    "--list-flavours",
    is_flag=True,
    help="List available flavour",
)
@click.option(
    "-Fb",
    "--list-base-flavours",
    is_flag=True,
    help="List available base flavour",
)
# TOREMOVE
# @click.option(
#    "--copy-from-store",
#    "-c",
#    is_flag=True,
#    help="Copy artifacts (initrd, kernels, ...) from Nix store to artifact directory",
# )
@click.option("--show-trace", is_flag=True, help="Show Nix trace")
@click.option(
    "--dry-run", is_flag=True, help="Show what this command would do without doing it"
)
@click.option(
    "--dry-build",
    is_flag=True,
    help="Eval build expression and show store entry without building derivation",
)
@click.option(
    "-C",
    "--composition-flavour",
    type=click.STRING,
    help="Use to specify which composition and flavour combination to build when multiple compositions are describe at once (see -L options to list them).",
)
@click.option(
    "-L",
    "--list-compositions-flavours",
    is_flag=True,
    help="List available combinations of compositions and flavours",
)
@click.option(
    "-s",
    "--setup",
    type=click.STRING,
    help="Select setup variant",
)
@click.option(
    "-p",
    "--setup-param",
    type=click.STRING,
    multiple=True,
    help="Override setup parameter",
)
@click.option(
    "-u",
    "--update-flake",
    is_flag=True,
    help="Update flake.lock equivalent to: nix flake update",
)
@click.option(
    "--monitor",
    is_flag=True,
    help="Build with nix-output-monitor",
)
@click.option(
    "--mounted-store-url",
    "--mu",
    type=click.STRING,
    help="Use of nix experimental SSH store with filesystem mounted, format: [username@]hostname",
)
@pass_context
@on_finished(lambda ctx: ctx.show_elapsed_time())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(
    ctx,
    composition_file,
    nix_flags,
    out_link,
    flavour,
    list_flavours,
    list_base_flavours,
    show_trace,
    dry_run,
    dry_build,
    composition_flavour,
    list_compositions_flavours,
    update_flake,
    setup,
    setup_param,
    monitor,
    mounted_store_url,
):
    """
    Builds the composition.

    It generates a `build` folder which stores symlinks to the closure associated to a composition. The file name of the symlink follows this structure  `[composition-name]::[flavour]`

    ## Examples

    - `nxc build -f vm`

        Build the `vm` flavour of your composition.

    - `nxc build -C oar::g5k-nfs-store`

        Build the `oar` composition with the `g5k-nfs-store` flavour.
    """

    def determine_flavour(ctx):
        if "default_flavour" in ctx.nxc and ctx.nxc["default_flavour"]:
            flavour = ctx.nxc["default_flavour"]
        else:
            platform_detection(ctx)
            if ctx.platform:
                flavour = ctx.platform.default_flavour
            else:
                flavour = "default"
        ctx.vlog(f"Selected flavour: {flavour}")
        return flavour

    if setup and not op.exists(op.join(ctx.envdir, "setup.toml")):
        ctx.elog("setup option is given but setup.toml is not found")
        sys.exit(1)

    if setup or op.exists(op.join(ctx.envdir, "setup.toml")):
        nix_flags, composition_file, composition_flavour, flavour, _ = apply_setup(
            ctx,
            setup,
            nix_flags,
            composition_file,
            composition_flavour,
            flavour,
            setup_param,
            None,
        )

    build_cmd = []

    # Do we are in flake context
    if not op.exists(op.join(ctx.envdir, "flake.nix")):
        ctx.elog("Not Found flake.nix file")
        sys.exit(1)

    if monitor:
        nix_cmd_base = ["nom"]
    else:
        nix_cmd_base = get_nix_command(ctx)

    if update_flake:
        cmd = nix_cmd_base + ["flake", "update"]
        if ctx.show_spinner:
            ctx.spinner.start("Updating flake.lock")
            ret = subprocess.call(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=ctx.envdir,
            )
            if ret:
                ctx.spinner.stop()
                ctx.elog("Updating flake.lock is failed")
                sys.exit(1)
            else:
                ctx.spinner.succeed("Updating flake.lock is done")

    description_flavours = get_flavours(nix_cmd_base, ctx)

    flavours = list(description_flavours.keys())

    if list_flavours:
        ctx.log("Flavours List:")
        for k in flavours:
            click.echo(f"{k: <18}: {description_flavours[k]['description']}")
        sys.exit(0)

    if list_base_flavours:
        flavours = get_base_flavours()
        for flavour in flavours:
            click.echo(f"{flavour['name']: <18}: {flavour['description']}")
        sys.exit(0)

    if not composition_file:
        composition_file = ctx.nxc["composition"]

    if list_compositions_flavours:
        cmd = nix_cmd_base + ["flake", "show", "--json"]
        raw_compositions_flavours = json.loads(
            subprocess.check_output(cmd, cwd=ctx.envdir).decode()
        )
        for compo_flavour in filter(
            lambda x: x not in ["flavoursJson", "showFlavours"],
            raw_compositions_flavours["packages"]["x86_64-linux"].keys(),
        ):
            print(compo_flavour)
        print(
            click.style("Default", fg="green")
            + ": "
            + raw_compositions_flavours["defaultPackage"]["x86_64-linux"]["name"]
        )
        sys.exit(0)

    if show_trace:
        build_cmd += ["--show-trace"]

    if mounted_store_url:
        build_cmd = [
            "--extra-experimental-features",
            "mounted-ssh-store",
            "--store",
            f"mounted-ssh-ng://{mounted_store_url}",
        ]

    if flavour and composition_flavour:
        if len(composition_flavour.split("::")) == 1:
            composition_flavour = composition_flavour + "::" + flavour

    if not out_link:
        build_path = op.join(ctx.envdir, "build")
        if not op.exists(build_path):
            create = click.style("   create", fg="green")
            ctx.log("   " + create + "  " + build_path)
            os.mkdir(build_path)

        if composition_flavour:
            if flavour and flavour != composition_flavour.split("::")[-1]:
                raise ValueError(
                    "the value of flavour  does not match  the ones of composition_favour"
                )

            ctx.composition_flavour_prefix = composition_flavour
            ctx.flavour_name = composition_flavour[-1]

        else:
            composition_name = (os.path.basename(composition_file)).split(".")[0]
            ctx.composition_name = composition_name
            if not flavour:
                flavour = determine_flavour(ctx)
            ctx.flavour_name = flavour
            ctx.composition_flavour_prefix = f"{composition_name}::{flavour}"

        out_link = op.join(build_path, ctx.composition_flavour_prefix)

    if not flavour:
        flavour = determine_flavour(ctx)

    if not composition_flavour:
        composition_flavour = f"composition::{flavour}"

    if dry_build:
        build_cmd = nix_cmd_base + ["eval"] + build_cmd + ["--raw"]
    else:
        build_cmd = nix_cmd_base + ["build"] + build_cmd
        if out_link and not mounted_store_url:
            build_cmd += ["-o", out_link]
        if mounted_store_url:
            build_cmd += ["--no-link", "--json"]

    # add additional nix flags if any
    if nix_flags:
        build_cmd += nix_flags.split()

    build_cmd += [f".#packages.x86_64-linux.{composition_flavour}"]

    if not dry_run:
        ctx.glog("Starting Build")
        ctx.vlog(build_cmd)
        if mounted_store_url:
            proc = subprocess.run(build_cmd, cwd=ctx.envdir, stdout=subprocess.PIPE)
            returncode = proc.returncode
            if not returncode:
                nix_build_output = json.loads(proc.stdout)
                # create link here and not by nix, to avoid issue directory is not accessible with remote build .
                ctx.vlog(f"nix build output: {nix_build_output}")
                if os.path.exists(out_link):
                    os.remove(out_link)
                shutil.copyfile(nix_build_output[0]["outputs"]["out"], out_link)

                if flavour == "g5k-nfs-store":
                    ctx.compose_info_file = out_link
                    artifact_copy_all_kernel_initrd(ctx)
        else:
            returncode = subprocess.call(build_cmd, cwd=ctx.envdir)
        if returncode:
            ctx.elog(f"Build return code: {returncode}")
            sys.exit(returncode)

        # Loading the docker image
        # todo: to move in docker flavour class
        if flavour == "docker" and not dry_build:
            out_link = realpath_from_store(ctx, out_link)
            with open(out_link, "r") as compose_info_json:
                content = json.load(compose_info_json)
                docker_image = realpath_from_store(ctx, content["image"])
                docker_load_command = f"docker load < {docker_image}"
                returncode = subprocess.call(docker_load_command, shell=True)
                if returncode:
                    ctx.elog(f"Build return code: {returncode}")
                    sys.exit(returncode)
            ctx.glog("Docker Image loaded")

        ctx.glog("\nBuild completed")
    else:
        ctx.log("Dry-run:")
        ctx.log(f"   working directory:          {ctx.envdir}")
        ctx.log(f"   composition flavour prefix: {ctx.composition_flavour_prefix}")
        ctx.log(f"   build command:              {' '.join(build_cmd)}")


def get_flavours(nix_cmd_base, ctx):
    """
    Returns the json representation of the available flavours
    """
    FLAVOURS_JSON = op.abspath(
        op.join(op.dirname(__file__), "../../nix", "flavours.json")
    )

    output_json = FLAVOURS_JSON

    # TODO add option to build flavours list from nix
    #
    # flake_location = "."
    # output_json = "/tmp/.flavours.json"
    # ctx.log("Build list of flavours")
    # retcode = subprocess.call(
    #     nix_cmd_base + ["build", f"{flake_location}#flavoursJson", "-o", output_json],
    #     stdout=subprocess.DEVNULL,
    #     stderr=subprocess.DEVNULL,
    # )
    # if retcode:
    #     output_json = FLAVOURS_JSON
    # else:
    #     if not op.exists(output_json):
    #         output_json = realpath_from_store(ctx, output_json)

    return json.load(open(output_json, "r"))


def get_base_flavours():
    return base_flavours
