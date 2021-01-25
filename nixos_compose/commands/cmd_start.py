import click

# import time
import os

import os.path as op
import subprocess

from ..context import pass_context, on_finished, on_started

from ..actions import (
    read_compose_info,
    read_test_script,
    generate_deploy_info_b64,
    generate_deployment,
    generate_kexec_scripts,
    launch_driver_vm,
    get_hosts_ip,
    launch_ssh_kexec,
)
from ..httpd import HTTPDaemon


@click.command("start")
@click.option("-r", "--driver-repl", is_flag=True, help="driver repl")
@click.option(
    "-f",
    "--machines-file",
    type=click.Path(exists=True, resolve_path=True),
    help="file that contains remote machines names to (duplicates are considered as one).",
)
@click.option(
    "-s",
    "--ssh",
    type=click.STRING,
    default="ssh",
    help="specify particular ssh command",
)
@click.option("-S", "--sudo", type=click.STRING, help="specify particular sudo commmad")
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, driver_repl, machines_file, ssh, sudo):
    """Build multi Nixos composition."""
    ctx.log("Starting")

    if not ctx.state["built"]:
        raise click.ClickException(
            "You need build composition first, with nxc build command"
        )

    nixos_test_driver = op.join(ctx.envdir, "result/bin/nixos-test-driver")
    if op.isfile(nixos_test_driver):
        if machines_file:
            raise click.ClickException(
                "Nixos Driver detected, --machines-files can not by use here."
            )
        ctx.log("Nixos Driver detected")
        if not driver_repl:
            test_script = read_test_script(op.join(ctx.envdir, "result/test-script"))
            os.environ["tests"] = test_script
        if "QEMU_OPTS" in os.environ:
            qemu_opts = os.environ["QEMU_OPTS"]
        else:
            qemu_opts = ""
        os.environ["QEMU_OPTS"] = f"{qemu_opts} -nographic"
        subprocess.call(nixos_test_driver, shell=True)
        # subprocess.run(nixos_test_driver)
        exit(0)

    ctx.log("Generate: deployment.json")
    compose_info = read_compose_info(ctx)

    flavour = None
    if "flavour" in compose_info:
        flavour = compose_info["flavour"]

    ips = None

    if machines_file:
        (ips, host2ip) = get_hosts_ip(machines_file)
        print(ips, host2ip)

    deployment, ips = generate_deployment(ctx, compose_info, ips)

    if machines_file:
        deployinfo_b64 = generate_deploy_info_b64(ctx, deployment)
        generate_kexec_scripts(ctx, deployment, deployinfo_b64)
        launch_ssh_kexec(ctx, deployment, ssh, sudo)
        exit(0)

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
