import click

import time

from ..context import pass_context, on_finished, on_started

from ..actions import (
    read_compose_info,
    read_test_script,
    generate_deployment_vm,
    launch_vm,
    wait_ssh_ports,
    launch_driver_vm,
)
from ..httpd import HTTPDaemon


@click.command("start")
@click.option("-d", "--driver-repl", is_flag=True, help="driver repl")
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, driver_repl):
    """Build multi Nixos composition."""
    ctx.log("Starting")

    ctx.log("Generate: deployment.json")
    compose_info = read_compose_info(ctx)

    flavour = None
    if "flavour" in compose_info:
        flavour = compose_info["flavour"]

    deployment, ips = generate_deployment_vm(ctx, compose_info)

    use_remote_deployment = False
    if use_remote_deployment:
        httpd = HTTPDaemon()
        ctx.log(f"Launch httpd: port: {httpd.port}")
        httpd.start()

    test_script = read_test_script(compose_info)
    launch_driver_vm(ctx, deployment, flavour, ips, 0, driver_repl, test_script)
    # launch_vm(ctx, deployment, 0)
    # wait_ssh_ports(ctx, ips, False)
    # httpd.stop()

    ctx.glog("That's All Folk")
