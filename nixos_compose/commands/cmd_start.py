import click

# import time
import os

import os.path as op
import subprocess

from ..context import pass_context, on_finished, on_started

from ..actions import (
    read_test_script,
    generate_deployment_info,
    generate_kexec_scripts,
    get_hosts_ip,
    # launch_ssh_kexec,
)
from ..httpd import HTTPDaemon
from ..driver import driver

DRIVER_MODES = {
    "vm-ssh": {"name": "vm-ssh", "vm": True, "shell": "ssh"},
    "vm": {"name": "vm", "vm": True, "shell": "chardev"},
    "remote": {"name": "ssh", "vm": False, "shell": "ssh"},
}

# def launch_driver_vm(
#     ctx, httpd_port=0, driver_repl=False, test_script=None
# ):
#     ctx.mode = DRIVER_MODES["vm"]
#     driver_mode(ctx,  driver_repl, test_script)
#     # driver_vm(deployment, ips, test_script)

# def launch_driver_ssh(
#     ctx, httpd_port, driver_repl, test_script
# ):
#     ctx.mode = DRIVER_MODES["remote"]
#     driver_mode(ctx, driver_repl, test_script)


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

    ctx.ssh = ssh
    ctx.sudo = sudo

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

    if machines_file:
        get_hosts_ip(ctx, machines_file)
        print(ctx.ip_addresses, ctx.host2ip_address)

    generate_deployment_info(ctx)

    if machines_file:
        generate_kexec_scripts(ctx)
        # launch_ssh_kexec(ctx, deployment, None, ssh, sudo)
        # exit(0)

    use_remote_deployment = False
    if use_remote_deployment:
        httpd = HTTPDaemon()
        ctx.log(f"Launch httpd: port: {httpd.port}")
        httpd.start()

    test_script = read_test_script(ctx.compose_info)

    if machines_file:
        ctx.mode = DRIVER_MODES["remote"]
        # launch_driver_ssh(ctx, 0, driver_repl, test_script)
    else:
        ctx.mode = DRIVER_MODES["vm"]
        # launch_driver_vm(ctx, 0, driver_repl, test_script)
    driver(ctx, driver_repl, test_script)
    # launch_vm(ctx, deployment, 0)
    # wait_ssh_ports(ctx, ips, False)
    # httpd.stop()

    ctx.glog("That's All Folk")
