import click

# import time
import os

import os.path as op
import subprocess

import pyinotify
import asyncio

from ..context import pass_context, on_finished, on_started

from ..actions import (
    read_test_script,
    generate_deployment_info,
    generate_kexec_scripts,
    get_hosts_ip,
    launch_ssh_kexec,
)

# from ..httpd import HTTPDaemon
from ..driver import driver

DRIVER_MODES = {
    "vm-ssh": {"name": "vm-ssh", "vm": True, "shell": "ssh"},
    "vm": {"name": "vm", "vm": True, "shell": "chardev"},
    "remote": {"name": "ssh", "vm": False, "shell": "ssh"},
}

machines_file_towait = ""
notifier = None


class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        if event.pathname == machines_file_towait:
            notifier.loop.stop()


@click.command("start")
@click.option("-r", "--driver-repl", is_flag=True, help="driver repl")
@click.option(
    "-f",
    "--machines-file",
    type=click.Path(resolve_path=True),
    help="file that contains remote machines names to (duplicates are considered as one).",
)
@click.option("-w", "--wait", is_flag=True, help="wait machnes-files creation")
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
def cli(ctx, driver_repl, machines_file, wait, ssh, sudo):
    """Start multi Nixos composition."""
    ctx.log("Starting")

    ctx.ssh = ssh
    ctx.sudo = sudo

    if not ctx.state["built"]:
        raise click.ClickException(
            "You need build composition first, with nxc build command"
        )

    if not wait and not op.isfile(machines_file):
        raise click.ClickException(f"{machines_file} file does not exist")

    if wait:
        if not machines_file:
            raise click.ClickException(
                "You need to provide --machines-files option with --wait"
            )

        if not op.isfile(machines_file):
            ctx.log(f"Waiting {machines_file} file creation")

            wm = pyinotify.WatchManager()  # Watch Manager
            loop = asyncio.get_event_loop()

            global notifier
            notifier = pyinotify.AsyncioNotifier(
                wm, loop, default_proc_fun=EventHandler()
            )

            global machines_file_towait
            machines_file_towait = machines_file

            # TODO race condition remains possible ....
            wm.add_watch(op.dirname(machines_file), pyinotify.IN_CREATE)
            loop.run_forever()
            notifier.stop()
            ctx.log(f"{machines_file} file created")

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
        exit(0)

    ctx.log("Generate: deployment.json")

    if machines_file:
        get_hosts_ip(ctx, machines_file)
        print(ctx.ip_addresses, ctx.host2ip_address)

    generate_deployment_info(ctx)

    if machines_file:
        generate_kexec_scripts(ctx)
        if not driver_repl:
            launch_ssh_kexec(ctx)
            exit(0)

    # use_remote_deployment = False
    # if use_remote_deployment:
    #     httpd = HTTPDaemon()
    #     ctx.log(f"Launch httpd: port: {httpd.port}")
    #     httpd.start()

    test_script = read_test_script(ctx.compose_info)

    if machines_file:
        ctx.mode = DRIVER_MODES["remote"]
    else:
        ctx.mode = DRIVER_MODES["vm"]

    driver(ctx, driver_repl, test_script)
    # launch_vm(ctx, deployment, 0)
    # wait_ssh_ports(ctx, ips, False)
    # httpd.stop()

    ctx.glog("That's All Folk")
