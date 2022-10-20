import click

import time
import os

import os.path as op
import subprocess
import sys
import glob
import pyinotify
import asyncio
import re
import tempfile
import ptpython.repl
from halo import Halo

from ..context import pass_context, on_finished, on_started
from ..flavours import get_flavour_by_name

from ..actions import (
    read_test_script,
    read_hosts,
    translate_hosts2ip,
    push_on_machines,
    realpath_from_store,
    get_fs_type,
)

from ..driver.driver import Driver
from ..httpd import HTTPDaemon

machines_file_towait = ""
notifier = None


class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        if event.pathname == machines_file_towait:
            notifier.loop.stop()


# TODO define scope of dry_run, must you dry_run deployment file creation ?
# Also how to address driver part
# def dry_run_print(ctx, launch_cmd):
#     ctx.log("Dry-run:")
#     ctx.log("   launch command:              {launch_cmd}")
@click.command("start")
@click.option(
    "-I",
    "--interactive",
    is_flag=True,
    help="drop into a python repl with driver functions",
)
@click.option(
    "-F",
    "--forward-ssh-port",
    is_flag=True,
    help="forward ssh port with nixos-test-driver forward-ssh-port",
)
@click.option(
    "-m",
    "--machines-file",
    type=click.Path(resolve_path=True),
    help="file that contains remote machines names to (duplicates are considered as one).",
)
@click.option(
    "-W", "--wait-machine-file", is_flag=True, help="wait machnes-file creation"
)
@click.option(
    "-s",
    "--ssh",
    type=click.STRING,
    default="ssh -l root ",
    help="specify particular ssh command",
)
@click.option(
    "-S",
    "--sudo",
    type=click.STRING,
    default="sudo",
    help="specify particular sudo command",
)
@click.option(
    "-p",
    "--push-path",
    help="remote path where to push image, kernel and kexec_script on machines (use to re-kexec)",
)
@click.option(
    "--reuse",
    is_flag=True,
    help="supposed a previous succeded start (w/ root access via ssh)",
)
@click.option(
    "--remote-deployment-info",
    is_flag=True,
    help="deployement info is served by http (in place of kernel parameters)",
)
@click.option(
    "-c",
    "-C",
    "--composition",
    type=click.STRING,
    help="specify composition, can specify flavour e.g. composition::flavour",
)
@click.option(
    "-f", "--flavour", type=click.STRING, help="specify flavour",
)
@click.option(
    "-t", "--test-script", is_flag=True, help="execute testscript",
)
@click.option(
    "--file-test-script", type=click.STRING, help="alternative testscript",
)
@click.option(
    "-w",
    "--sigwait",
    is_flag=True,
    help="wait any signal to exit after a start only action (not testscript execution or interactive use)",
)
@click.argument(
    "roles_quantities_file", required=False, default=None, type=click.Path(exists=True)
)
# @click.option(
#     "--dry-run", is_flag=True, help="Show what this command would do without doing it"
# )
@pass_context
@on_finished(lambda ctx: ctx.show_elapsed_time())
@on_started(lambda ctx: ctx.assert_valid_env())
def cli(
    ctx,
    interactive,
    machines_file,
    wait_machine_file,
    ssh,
    sudo,
    push_path,
    forward_ssh_port,
    reuse,
    composition,
    flavour,
    remote_deployment_info,
    test_script,
    file_test_script,
    sigwait,
    roles_quantities_file
    # dry_run,
):
    """Start Nixos Composition."""
    flavour_name = flavour
    if test_script:
        execute_test_script = True
        test_script = None
    else:
        execute_test_script = False

    if file_test_script:
        raise click.ClickException(
            "alternative test-scipt execution not yet implemented"
        )

    ctx.log("Starting")

    ctx.ssh = ssh
    ctx.sudo = sudo
    ctx.push_path = push_path
    ctx.interactive = interactive
    ctx.execute_test_script = execute_test_script
    ctx.sigwait = sigwait

    if remote_deployment_info:
        ctx.use_httpd = True

    build_path = op.join(ctx.envdir, "build")

    if not op.exists(build_path):
        raise click.ClickException(
            "You need build composition first, with nxc build command"
        )

    # Handle cases where machines list must be provided
    machines = []
    if machines_file and not op.isfile(machines_file) and not wait_machine_file:
        raise click.ClickException(f"{machines_file} file does not exist")

    if push_path and not machines_file:
        raise click.ClickException("machines_file must be provide to use push_path")

    if wait_machine_file:
        if not machines_file:
            raise click.ClickException(
                "You need to provide --machines-file option with --wait"
            )

        if not op.isfile(machines_file):
            # ctx.log(f"Waiting {machines_file} file creation")
            # TODO: add quiet option
            spinner = Halo(text=f"Waiting for {machines_file} creation", spinner="dots")
            spinner.start()

            if "nfs" == get_fs_type(machines_file):
                while not op.isfile(machines_file):
                    time.sleep(0.1)
            else:
                wm = pyinotify.WatchManager()  # Watch Manager
                loop = asyncio.get_event_loop()

                global notifier
                notifier = pyinotify.AsyncioNotifier(
                    wm, loop, default_proc_fun=EventHandler()
                )

                global machines_file_towait
                machines_file_towait = machines_file

                # TODO race condition remains possible ....
                wm.add_watch(op.dirname(machines_file), pyinotify.CREATE)
                loop.run_forever()
                notifier.stop()

            # ctx.log(f"{machines_file} file created")
            spinner.succeed(f"{machines_file} file created")

    # Determine composition and flavour name
    # First case composition is given not flavour name
    if composition and (flavour_name is None):
        splitted_composition = composition.split("::")
        len_splitted_composition = len(splitted_composition)
        if len_splitted_composition == 2:

            composition_name, flavour_name = splitted_composition
            composition_all_in_one_file = op.join(ctx.envdir, f"build/::{flavour_name}")

            if not op.lexists(composition_all_in_one_file):
                build_path = op.join(ctx.envdir, f"build/{composition}")
                if not op.lexists(build_path):
                    raise click.ClickException(
                        f"Build file does not exist: {build_path}"
                    )
            else:
                build_path = composition_all_in_one_file

            ctx.flavour = get_flavour_by_name(flavour_name)(ctx)
            ctx.composition_name = composition_name
            ctx.composition_flavour_prefix = composition
            ctx.composition_basename_file = composition_name
        else:
            raise Exception(
                "Sorry, provide only flavour or only composition is not supported"
            )

    if composition is None:
        if flavour_name:
            search_path = f"{build_path}/*::{flavour_name}"
        else:
            search_path = f"{build_path}/*"

        build_paths = glob.glob(search_path)
        if not build_paths:
            raise click.ClickException("Failed to find last build")

        last_build_path = max(
            build_paths, key=lambda x: os.stat(x, follow_symlinks=False).st_ctime,
        )

        ctx.log("Use last build:")
        ctx.glog(last_build_path)

        build_path = last_build_path
        ctx.composition_flavour_prefix = op.basename(last_build_path)

        splitted_basename = ctx.composition_flavour_prefix.split("::")

        if splitted_basename[0] == "":
            raise click.ClickException("Sorry, composition name must be provided")

        ctx.composition_name = splitted_basename[0]
        ctx.composition_basename_file = ctx.composition_name

        if flavour_name:
            assert flavour_name == splitted_basename[1]

        ctx.flavour = get_flavour_by_name(splitted_basename[1])(ctx)

    if op.isdir(build_path) and len(os.listdir(build_path)) == 0:
        ctx.wlog(f"{build_path} is an empty directory, surely a nixos-test result !")
        sys.exit(2)

    ctx.compose_info_file = realpath_from_store(ctx, build_path)
    # TODO remove only available in nixpkgs version 20.03 and before
    # if build is nixos_test result open log.html
    nixos_test_log = op.join(build_path, "log.html")
    if op.exists(nixos_test_log) and op.isfile(nixos_test_log):
        subprocess.call(f"xdg-open {nixos_test_log}", shell=True)
        sys.exit(0)

    nixos_test_driver = op.join(build_path, "bin/nixos-test-driver")
    if op.exists(nixos_test_driver) and op.isfile(nixos_test_driver):
        test_script = None
        # Deduce which nixos_test_driver is used (WARNNING: very fragile)
        with open(nixos_test_driver) as f:
            driver_script = f.read()

        after_nixos_21_05 = False

        if "startScript" in driver_script:
            after_nixos_21_05 = True
            ctx.vlog("Detected Nixos Test Driver post 21.05")
        else:
            ctx.vlog("Detected Nixos Test Driver pre 21.11")

        if machines_file:
            raise click.ClickException(
                "Nixos Driver detected, --machines-files can not by use here."
            )
        ctx.log("Nixos Driver detected")

        if not interactive:
            test_script = read_test_script(ctx, op.join(build_path, "test-script"))

        if forward_ssh_port:
            ctx.forward_ssh_port = True
            test_script = "start_all(); [m.forward_port(22022+i, 22) for i, m in enumerate(machines)]; join_all();"
            nodes = [n.split("-")[1] for n in re.findall(r"run-\w+-vm", driver_script)]

            if not ctx.compose_info:
                ctx.compose_info = {}
            ctx.compose_info["nodes"] = nodes

            ctx.flavour.generate_deployment_info()

        if "QEMU_OPTS" in os.environ:
            qemu_opts = os.environ["QEMU_OPTS"]
        else:
            qemu_opts = ""
        os.environ["QEMU_OPTS"] = f"{qemu_opts} -nographic"
        print(f"qemu_opts: {qemu_opts}")
        print(f"cmd: {nixos_test_driver}")

        if not test_script:
            ctx.wlog("Not test_script provided")

        cmd = nixos_test_driver

        if not after_nixos_21_05:
            if test_script:
                os.environ["tests"] = test_script
            subprocess.call(cmd)
        else:
            if interactive:
                cmd = f"{cmd} -I"
            if test_script:
                with tempfile.NamedTemporaryFile() as tmp:
                    ctx.vlog(f"Create temporay test_script {tmp.name}")
                    tmp.write(test_script.encode())
                    tmp.seek(0)
                    subprocess.call(f"{cmd} {tmp.name}", shell=True)
            else:
                subprocess.call(cmd, shell=True)
        sys.exit(0)

    # if not machines_file and ctx.platform:
    # TODO
    # machines = ctx.platform.retrieve_machines(ctx)
    # import pdb; pdb.set_trace()
    if ctx.platform:
        if reuse:
            (ssh, sudo, push_path) = ctx.platform.subsequent_start_values
        else:
            (ssh, sudo, push_path) = ctx.platform.first_start_values
        if ctx.push_path is None:
            ctx.push_path = push_path

    if machines_file:
        machines = read_hosts(machines_file)

    if machines:
        translate_hosts2ip(ctx, machines)
        print(ctx.ip_addresses, ctx.host2ip_address)

    if roles_quantities_file:
        ctx.load_role_quantities_file(roles_quantities_file)

    ctx.flavour.generate_deployment_info()

    if ctx.ip_addresses and (ctx.flavour.name != "vm-ramdisk"):
        if ctx.use_httpd:
            ctx.vlog("Launch: httpd to distribute deployment.json")
            ctx.httpd = HTTPDaemon(ctx=ctx)

        if hasattr(ctx.flavour, "generate_kexec_scripts"):
            ctx.flavour.generate_kexec_scripts()

        if ctx.push_path:
            push_on_machines(ctx)

        if ctx.use_httpd:
            ctx.httpd.start(directory=ctx.envdir)

        if not interactive:
            ctx.flavour.launch()
            sys.exit(0)
            # if ctx.flavour["image"]["type"] == "ramdisk":
            #     ctx.log("Launch ssh(s) kexec")
            #     launch_ssh_kexec(ctx)
            #     time.sleep(10)
            #     wait_ssh_ports(ctx)
            #     sys.exit(0)
            # if ctx.flavour_name == "g5k-image":
            #     generate_kadeploy_envfile(ctx)
            #     launch_kadeploy(ctx)
            #     sys.exit(0)

    # elif ctx.flavour_name == "docker":
    #     ctx.mode = DRIVER_MODES["docker"]
    # else:
    #     ctx.mode = DRIVER_MODES["vm"]

    # use_remote_deployment = False
    # if use_remote_deployment:
    #     httpd = HTTPDaemon()
    #     ctx.log(f"Launch httpd: port: {httpd.port}")
    #     httpd.start()

    test_script = read_test_script(ctx, ctx.compose_info)

    if forward_ssh_port:
        # ctx.mode = DRIVER_MODES["vm-ssh"]
        ctx.forward_ssh_port = forward_ssh_port
        test_script = None

    # driver(ctx, driver_repl, test_script)
    # launch_vm(ctx, deployment, 0)
    # wait_ssh_ports(ctx, ips, False)
    # httpd.stop()

    if not interactive and not execute_test_script:
        test_script = "start_all()"

    with Driver(
        # args.start_scripts, args.vlans, args.testscript.read_text(), args.keep_vm_state
        ctx,
        [],
        [],
        test_script,
        False,
    ) as driver:
        if interactive:
            ptpython.repl.embed(driver.test_symbols(), {})
        elif execute_test_script:
            tic = time.time()
            driver.run_tests()
            toc = time.time()
            ctx.glog(f"test script finished in {(toc-tic):.2f}s")
        else:
            ctx.glog("just start ???")
            driver.test_script()
    if ctx.use_httpd:
        ctx.httpd.stop()

    ctx.glog("That's All Folk")
