import click

import time
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
    read_hosts,
    translate_hosts2ip,
    push_on_machines,
    launch_ssh_kexec,
    wait_ssh_ports,
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
    "-F",
    "--forward-ssh-port",
    is_flag=True,
    help="forward ssh port with nixos-test-driver forward-ssh-port",
)
@click.option(
    "-f",
    "--machines-file",
    type=click.Path(resolve_path=True),
    help="file that contains remote machines names to (duplicates are considered as one).",
)
@click.option("-w", "--wait", is_flag=True, help="wait machnes-files creation")
@click.option(
    "-s", "--ssh", type=click.STRING, help="specify particular ssh command",
)
@click.option("-S", "--sudo", type=click.STRING, help="specify particular sudo command")
@click.option(
    "-p",
    "--push-path",
    help="remote path where to push image, kernel and kexec_script on machines (use to re-kexec)",
)
@pass_context
@on_finished(lambda ctx: ctx.state.dump())
@on_finished(lambda ctx: ctx.show_elapsed_time())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(ctx, driver_repl, machines_file, wait, ssh, sudo, push_path, forward_ssh_port):
    """Start multi Nixos composition."""
    ctx.log("Starting")

    ctx.ssh = ssh
    ctx.sudo = sudo
    ctx.push_path = push_path

    machines = []

    if not ctx.state["built"]:
        raise click.ClickException(
            "You need build composition first, with nxc build command"
        )

    if machines_file and not op.isfile(machines_file):
        raise click.ClickException(f"{machines_file} file does not exist")

    if push_path and not machines_file:
        raise click.ClickException("machines_file must be provide to use push_path")

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

        elif forward_ssh_port:
            test_script = "start_all(); [m.forward_port(22022+i, 22) for i, m in enumerate(machines)]; join_all();"
            os.environ["tests"] = test_script
            import re

            with open("result/bin/nixos-test-driver") as f:
                driver_script = f.readlines()

            nodes = [
                n.split("-")[1] for n in re.findall(r"run-\w+-vm", driver_script[3])
            ]
            if not ctx.compose_info:
                ctx.compose_info = {}
            ctx.compose_info["nodes"] = nodes

            generate_deployment_info(ctx, forward_ssh_port=True)

        if "QEMU_OPTS" in os.environ:
            qemu_opts = os.environ["QEMU_OPTS"]
        else:
            qemu_opts = ""
        os.environ["QEMU_OPTS"] = f"{qemu_opts} -nographic"
        subprocess.call(nixos_test_driver, shell=True)
        exit(0)

    if not machines_file and ctx.platform:
        machines = ctx.platform.retrieve_machines(ctx)
        (ssh, sudo, push_path) = ctx.platform.get_start_values(ctx)
        if ctx.ssh is None:
            ctx.ssh = ssh
        if ctx.sudo is None:
            ctx.sudo = sudo
        if ctx.push_path is None:
            ctx.push_path = push_path

    elif machines_file:
        machines = read_hosts(machines_file)

    if machines:
        translate_hosts2ip(ctx, machines)
        print(ctx.ip_addresses, ctx.host2ip_address)

    ctx.log("Generate: deployment.json")
    generate_deployment_info(ctx)

    if (
        ctx.ip_addresses
        and ("vm" not in ctx.flavour)
        and ("vm" in ctx.flavour and not ctx.flavour.vm)
    ):
        generate_kexec_scripts(ctx)
        if ctx.push_path:
            push_on_machines(ctx)
        if not driver_repl:
            ctx.log("Launch ssh(s) kexec")
            launch_ssh_kexec(ctx)
            time.sleep(10)
            wait_ssh_ports(ctx)
            ctx.state["started"] = True
            exit(0)

    # use_remote_deployment = False
    # if use_remote_deployment:
    #     httpd = HTTPDaemon()
    #     ctx.log(f"Launch httpd: port: {httpd.port}")
    #     httpd.start()

    test_script = read_test_script(ctx.compose_info)

    if ctx.ip_addresses:
        ctx.mode = DRIVER_MODES["remote"]
    else:
        ctx.mode = DRIVER_MODES["vm"]

    ctx.mode = DRIVER_MODES["vm-ssh"]
    test_script = None

    driver(ctx, driver_repl, test_script)
    # launch_vm(ctx, deployment, 0)
    # wait_ssh_ports(ctx, ips, False)
    # httpd.stop()

    ctx.glog("That's All Folk")
