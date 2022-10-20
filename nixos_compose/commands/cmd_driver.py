import click
import json
import re
import sys
import ptpython.repl

from ..context import pass_context
from ..actions import read_deployment_info, realpath_from_store
from ..flavours import get_flavour_by_name

from ..driver.driver import Driver


@click.command("driver")
@click.option("-l", "--user", default="root")
@click.option(
    "-d",
    "--deployment-file",
    help="Deployment file, take the latest created in deploy directory by default",
)
@click.option(
    "-f",
    "--flavour",
    help="flavour, by default it's extracted from deployment file name",
)
@click.option(
    "-t", "--test-script", is_flag=True, help="execute the 'embedded' testscript",
)
@click.argument("test-script-file", required=False)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, deployment_file, flavour, test_script_file, test_script):
    """Start driver to intearct with deployed environment."""
    read_deployment_info(ctx, deployment_file)

    # determine flavour name
    if not flavour:
        match = re.match(r"^.*::(.+)\..*$", ctx.deployment_filename)
        if match:
            flavour = match.group(1)
        else:
            raise click.ClickException(
                "Cannot determined flavour, one must by provided (option fix deployment file name or use --flavour option"
            )

    ctx.flavour = get_flavour_by_name(flavour)(ctx)

    ctx.external_connect = True
    ctx.no_start = True

    # TODO add test to ssh port
    if test_script:
        if "test_script" in ctx.deployment_info:
            test_script_file = ctx.deployment_info["test_script"]

        elif "compositions_info_path" in ctx.deployment_info:
            compositions_info_file = realpath_from_store(
                ctx, ctx.deployment_info["compositions_info_path"]
            )
            with open(compositions_info_file, "r") as f:
                compositions_info = json.load(f)

            selected_composition = ctx.deployment_info["composition"]
            test_script_file = compositions_info[selected_composition]["test_script"]

        test_script_file = realpath_from_store(ctx, test_script_file)

    test_script_str = ""
    if test_script_file:
        test_script = True
        with open(test_script_file, "r") as f:
            test_script_str = f.read()

    if test_script and test_script_str == "":
        ctx.elog(f"test script ({test_script_file}) is empty")
        sys.exit(1)

    with Driver(
        # args.start_scripts, args.vlans, args.testscript.read_text(), args.keep_vm_state
        ctx,
        [],
        [],
        test_script_str,
        False,
    ) as driver:
        if test_script:
            try:
                driver.test_script()
            except Exception as e:
                ctx.elog(e)
                sys.exit(1)
        else:
            ptpython.repl.embed(driver.test_symbols(), {})
