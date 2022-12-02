import click

import time
import os

import os.path as op

import sys
import glob
import pyinotify
import asyncio

import ptpython.repl

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
from ..setup import apply_setup

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
    help="wait any signal to exit after a start only action (not testscript execution or interactive use",
)
@click.option(
    "-k",
    "--kernel-params",
    type=click.STRING,
    help="additional kernel parameters, this option is flavour dependent",
)
@click.option(
    "-r",
    "--role-distribution",
    multiple=True,
    help="specify the number of nodes or nodes' name for a role (e.g. compute=2 or server=foo,bar ).",
)
@click.argument(
    "roles_distribution_file",
    required=False,
    default=None,
    type=click.Path(exists=True),
)
@click.option(
    "--compose-info",
    type=click.Path(resolve_path=True),
    help="specific compose info file",
)
@click.option(
    "-s", "--setup", type=click.STRING, help="Select setup variant",
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
    reuse,
    composition,
    flavour,
    remote_deployment_info,
    test_script,
    file_test_script,
    sigwait,
    kernel_params,
    role_distribution,
    roles_distribution_file,
    compose_info,
    setup,
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
    ctx.set_roles_distribution(role_distribution, roles_distribution_file)

    # kernel_params can by setted through setup
    if setup or op.exists(op.join(ctx.envdir, "setup.toml")):
        _, _, _, _, kernel_params = apply_setup(
            ctx, setup, None, None, None, None, None, kernel_params,
        )
    ctx.kernel_params = kernel_params

    if remote_deployment_info:
        ctx.use_httpd = True

    build_path = op.join(ctx.envdir, "build")

    if not compose_info and not op.exists(build_path):
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
            if ctx.show_spinner:
                ctx.spinner.start(f"Waiting for {machines_file} creation")

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

            if ctx.show_spinner:
                ctx.spinner.succeed(f"{machines_file} file created")
            else:
                ctx.log(f"{machines_file} file created")

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

    if composition is None and compose_info is None:
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

    if not compose_info and op.isdir(build_path) and len(os.listdir(build_path)) == 0:
        ctx.wlog(f"{build_path} is an empty directory, surely a nixos-test result !")
        sys.exit(2)

    if (composition is None) and flavour_name and compose_info:
        ctx.flavour = get_flavour_by_name(flavour_name)(ctx)
        ctx.compose_info_file = realpath_from_store(ctx, compose_info)
        ctx.composition_flavour_prefix = op.basename(compose_info)
        ctx.composition_name = "composition"
        ctx.composition_basename_file = ctx.composition_name
    else:
        ctx.compose_info_file = realpath_from_store(ctx, build_path)

    if ctx.platform:
        if reuse:
            (ssh, sudo, push_path) = ctx.platform.subsequent_start_values
        else:
            (ssh, sudo, push_path) = ctx.platform.first_start_values
        if ctx.push_path is None:
            ctx.push_path = push_path

    if machines_file:
        machines = read_hosts(machines_file)
        if not machines:
            ctx.elog(f"Machine file '{machines_file}' is empty")
            sys.exit(1)

    if machines:
        translate_hosts2ip(ctx, machines)
        print(ctx.ip_addresses, ctx.host2ip_address)

    ctx.flavour.generate_deployment_info()

    if (
        ctx.ip_addresses
        and (ctx.flavour.name != "vm-ramdisk")
        and (ctx.flavour.name != "vm")
    ):
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

    test_script = read_test_script(ctx, ctx.compose_info)

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

    ctx.glog("Started")
