import os
import os.path as op
import json
import re
import subprocess
import sys

from io import open

import click

from ..actions import get_nix_command
from ..context import pass_context

from ..platform import platform_detection
from ..utils import copy_tree

NXC_NIX_PATH = op.abspath(op.join(op.dirname(__file__), "../../nix"))


@click.command("init")
# @click.option("-f", "--force", is_flag=True, help="Overwrite existing env")
@click.option(
    "--no-symlink",
    is_flag=True,
    help="Disable symlink creation to nxc.json (need to change directory for next command",
)
@click.option(
    "-n", "--disable-detection", is_flag=True, help="Disable platform detection."
)
@click.option(
    "-f",
    "--default-flavour",
    type=click.STRING,
    help="Set default flavour to build, if not given nixos-compose try to find a good",
)
@click.option(
    "--list-flavours-json",
    is_flag=True,
    help="List description of flavours, in json format",
)
@click.option(
    "-F", "--list-flavours", is_flag=True, help="List available flavour",
)
@click.option(
    "-t", "--template", default="basic", help="Use a template", show_default=True,
)
@click.option(
    "--use-local-templates",
    is_flag=True,
    default=False,
    help="Either use the local templates or not",
)
@click.option(
    "--list-templates-json",
    is_flag=True,
    default=False,
    help="Display the list of available templates as JSON",
)
@pass_context
# @on_finished(lambda ctx: ctx.state.dump())
def cli(
    ctx,
    no_symlink,
    disable_detection,
    default_flavour,
    list_flavours,
    list_flavours_json,
    template,
    use_local_templates,
    list_templates_json,
):
    """Initialize a new environment."""

    nix_cmd_base = get_nix_command(ctx)

    create = click.style("   create", fg="green")

    nxc_json_file = op.abspath(op.join(ctx.envdir, "nxc.json"))
    description_flavours_file = op.abspath(op.join(NXC_NIX_PATH, "flavours.json"))
    description_flavours = json.load(open(description_flavours_file, "r"))

    if list_flavours:
        for k in description_flavours.keys():
            click.echo(f"{k: <18}: {description_flavours[k]['description']}")
        sys.exit(0)

    if list_flavours_json:
        print(json.dumps(description_flavours, indent=4))
        sys.exit(0)

    if list_templates_json:
        out_file = "/tmp/.template_list.json"
        flake_location = (
            "."
            if use_local_templates
            else "git+https://gitlab.inria.fr/nixos-compose/nixos-compose"
        )
        subprocess.call(
            nix_cmd_base + ["build", f"{flake_location}#showTemplates", "-o", out_file],
            stdout=subprocess.DEVNULL,
            # stderr=subprocess.DEVNULL,
        )

        list_templates = json.load(open(out_file, "r"))
        print(json.dumps(list_templates, indent=4))
        sys.exit(0)

    if not disable_detection:
        platform_detection(ctx)

    flake_location = (
        "."
        if use_local_templates
        else "git+https://gitlab.inria.fr/nixos-compose/nixos-compose"
    )
    res = subprocess.run(
        nix_cmd_base + ["flake", "new", "-t", f"{flake_location}#{template}", "nxc"],
        capture_output=True,
    )
    # Workaround for nix 2.10.3 due to bug with flae new -t and store located in  ~/.local/share/nix/root
    # Should be resolved with availability of source tree abstraction
    # see https://github.com/NixOS/nix/pull/6530
    if res.returncode:
        # local_store_path can be present into one or three lines
        r = re.compile(".*local/share/nix/root/nix/store.*")
        res_error = res.stderr.decode()
        local_store_path = list(filter(r.match, res_error.split()))
        if local_store_path:
            copy_tree(local_store_path[0][1:-1], ctx.envdir)
            subprocess.run(["chmod", "-R", "gu+w", ctx.envdir])
        else:
            ctx.elog("Flake new from template failed:")
            ctx.elog(f"returncode: {res.returncode}")
            ctx.elog(f"stdout: {res.stdout.decode()}")
            ctx.elog(f"stderr: {res.stderr.decode()}")
            sys.exit(1)
    nxc_json = {
        "composition": "composition.nix",  # TODO to enhance
        "default_flavour": default_flavour,
    }

    if ctx.platform:
        nxc_json["platform"] = ctx.platform.name
        if not default_flavour:
            nxc_json["default_flavour"] = ctx.platform.default_flavour
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
