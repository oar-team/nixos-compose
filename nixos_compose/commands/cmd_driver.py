import click
import re
import ptpython.repl

from ..context import pass_context
from ..actions import read_deployment_info
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
@click.argument("test-script", required=False)
@pass_context
# TODO @on_finished(lambda ctx: ctx.state.dump())
# TODO @on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, user, deployment_file, flavour, test_script):
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

    test_script_str = ""
    if test_script:
        with open(test_script, "r") as f:
            test_script_str = f.read()

    with Driver(
        # args.start_scripts, args.vlans, args.testscript.read_text(), args.keep_vm_state
        ctx,
        [],
        [],
        test_script_str,
        False,
    ) as driver:
        if test_script:
            driver.test_script()
        else:
            ptpython.repl.embed(driver.test_symbols(), {})
