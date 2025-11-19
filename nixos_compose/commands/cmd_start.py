import click

import time
import os

import os.path as op

import sys
import glob

import ast
import json

import ptpython.repl

from ..context import pass_context, on_finished, on_started
from ..flavours import get_flavour_by_name

from ..actions import (
    read_deployment_info,
    read_test_script,
    push_on_machines,
    realpath_from_store,
)

from ..driver.driver import Driver
from ..httpd import HTTPDaemon
from ..setup import apply_setup


def start(ctx, interactive, execute_test_script, port, push_path=None):
    if (  # TODO rework (ask flavour ?)
        ctx.ip_addresses
        and (ctx.flavour.name != "vm-ramdisk")
        and (ctx.flavour.name != "vm")
    ) or ctx.flavour.name == "nspawn":
        if ctx.use_httpd:
            ctx.vlog("Launch: httpd to distribute deployment.json")
            ctx.httpd = HTTPDaemon(ctx=ctx, port=port)

        if hasattr(ctx.flavour, "generate_kexec_scripts"):
            ctx.flavour.generate_kexec_scripts()

        if push_path:
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
    "--machine-file",
    type=click.Path(resolve_path=True),
    help="file that contains remote machines names to (duplicates are considered as one).",
)
@click.option(
    "-W", "--wait-machine-file", is_flag=True, help="wait machine-file creation"
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
    "--http-deployment-info",
    is_flag=True,
    help="deployment info is served via http (in place of kernel parameters)",
)
@click.option(
    "--port",
    type=click.INT,
    default=0,
    help="Port to use for the HTTP server",
)
@click.option(
    "--image-store-ssh",
    type=click.STRING,
    help="(experimental, only for Grid'5000) [username@]hostname[:port]",
)
@click.option(
    "-c",
    "-C",
    "--composition",
    type=click.STRING,
    help="specify composition, can specify flavour e.g. composition::flavour",
)
@click.option(
    "-f",
    "--flavour",
    type=click.STRING,
    help="specify flavour",
)
@click.option(
    "-t",
    "--test-script",
    is_flag=True,
    help="execute testscript",
)
@click.option(
    "--file-test-script",
    type=click.STRING,
    help="alternative testscript",
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
    "-i",
    "--identity-file",
    type=click.STRING,
    help="path to the ssh public key to use to connect to the deployments",
)
@click.option(
    "-s",
    "--setup",
    type=click.STRING,
    help="Select setup variant",
)
@click.option(
    "-p",
    "--parameter",
    type=click.STRING,
    multiple=True,
    help="Parameter added to deployment file (for contextualization phase)",
)
@click.option(
    "-P",
    "--parameter-file",
    type=click.STRING,
    help="Json file contains parameters added to deployment file (for contextualization phase)",
)
@click.option(
    "-d",
    "--deployment-file",
    type=click.STRING,
    help="Deployement json file use for the deployment (skip generation) Warning parametrization not supported (upto now)",
)
@click.option(
    "--ip-range",
    type=click.STRING,
    default="",
    help="IP range (for now only usable with nspawn flavour)",
)
@click.option(
    "-a",
    "--tag",
    type=click.STRING,
    help="tagname of the deployment",
)
#     "--dry-run", is_flag=True, help="Show what this command would do without doing it"
# )
@pass_context
@on_finished(lambda ctx: ctx.show_elapsed_time())
@on_started(lambda ctx: ctx.warning_valid_env())
def cli(
    ctx,
    interactive,
    machine_file,
    wait_machine_file,
    ssh,
    sudo,
    push_path,
    reuse,
    composition,
    flavour,
    remote_deployment_info,
    port,
    test_script,
    file_test_script,
    sigwait,
    kernel_params,
    role_distribution,
    roles_distribution_file,
    compose_info,
    identity_file,
    setup,
    parameter,
    parameter_file,
    ip_range,
    deployment_file,
    tag,
    image_store_ssh,
    # dry_run,
):
    """
    Starts a set of nodes using the previous build.

    `ROLE_DISTRIBUTION_FILE` is and optional YAML file describing how many instances of each role are expected.

    ## Examples

    - `nxc start`

       Start the last built composition.

    - `nxc start role-distrib.yaml`

        With the file `role-distrib.yaml` written as this:

        ```yaml
        nfsServerNode: 1
        nfsClientNode: 2
        ```

        Instantiates two nodes with the role `nfsClientNode` and one only with the role `nfsServerNode`. Of course, these roles have to be described beforehand in a `composition.nix` file.

    """
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
    ctx.interactive = interactive
    ctx.execute_test_script = execute_test_script
    ctx.sigwait = sigwait
    ctx.ip_range = ip_range
    ctx.machine_file = machine_file
    ctx.image_store_ssh = image_store_ssh
    if deployment_file:
        if not flavour:
            ctx.elog("Option --flavour is required with --deployment-file option !")
            sys.exit(2)
        else:
            ctx.flavour = get_flavour_by_name(flavour_name)(ctx)
            read_deployment_info(ctx, deployment_file)

    if deployment_file and (role_distribution or roles_distribution_file):
        ctx.wlog(
            "--role-distribution and --roles-distribution-file are ignored with --deployment-file option !"
        )

    ctx.set_roles_distribution(role_distribution, roles_distribution_file)

    # kernel_params can by set through setup
    if setup or op.exists(op.join(ctx.envdir, "setup.toml")):
        _, _, _, _, kernel_params = apply_setup(
            ctx,
            setup,
            None,
            None,
            None,
            None,
            None,
            kernel_params,
        )
    ctx.kernel_params = kernel_params

    if remote_deployment_info:
        ctx.use_httpd = True

    if parameter_file:
        with open(parameter_file, "r") as f:
            try:
                ctx.deployment_info["parameters"] = json.load(f)
            except ValueError:
                raise click.ClickException(
                    f"Failed to parse parameters json file: {parameter_file}"
                )

    if parameter:
        if "parameters" not in ctx.deployment_info:
            ctx.deployment_info["parameters"] = {}
        for p in parameter:
            try:
                (k, v) = p.split("=", 1)
                v = ast.literal_eval(v)
            except ValueError:
                raise click.ClickException(f"Fail to parse parameter: {p}")
            ctx.deployment_info["parameters"][k] = v

    if deployment_file:
        start(ctx, interactive, execute_test_script, port, push_path)
        sys.exit(0)

    build_path = op.join(ctx.envdir, "build")

    if not compose_info and not op.exists(build_path):
        raise click.ClickException(
            "You need build composition first, with nxc build command"
        )

    # Handle cases where machines list must be provided
    if machine_file and not op.isfile(machine_file) and not wait_machine_file:
        raise click.ClickException(f"{machine_file} file does not exist")

    if push_path and not machine_file:
        raise click.ClickException("machine_file must be provided to use push_path")

    if wait_machine_file:
        if not machine_file:
            raise click.ClickException(
                "You need to provide --machine-file option with --wait"
            )

        if not op.isfile(machine_file):
            # ctx.log(f"Waiting {machine_file} file creation")
            # TODO: add quiet option
            if ctx.show_spinner:
                ctx.spinner.start(f"Waiting for {machine_file} creation")

            # Note: inotify approach does not work with NFS, and pyinotify
            # is no more developed so simple pulling loop is used
            # if "nfs" == get_fs_type(machine_file):
            while not op.isfile(machine_file):
                time.sleep(0.1)

            if ctx.show_spinner:
                ctx.spinner.succeed(f"{machine_file} file created")
            else:
                ctx.log(f"{machine_file} file created")

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
            ctx.composition_flavour_prefix = (
                (composition + "::" + tag) if tag else composition
            )
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
            build_paths,
            key=lambda x: os.stat(x, follow_symlinks=False).st_ctime,
        )

        ctx.log("Use last build:")
        ctx.glog(last_build_path)

        build_path = last_build_path
        ctx.composition_flavour_prefix = (
            (op.basename(last_build_path) + "::" + tag)
            if tag
            else str(op.basename(last_build_path))
        )

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
        ctx.composition_flavour_prefix = (
            (op.basename(compose_info) + "::" + tag)
            if tag
            else op.basename(compose_info)
        )
        ctx.composition_name = "composition"
        ctx.composition_basename_file = ctx.composition_name
    else:
        ctx.compose_info_file = realpath_from_store(ctx, build_path)

    #
    # ssh not used, subsequent_start_values and first_start_values not use w/
    # nfs mount on g5k. If not need on other platform to REMOVE (see also platform.py
    # Only depends of flavours or plaforms
    #
    # if ctx.platform:
    #     if reuse:
    #         (ssh, sudo, push_path) = ctx.platform.subsequent_start_values
    #     else:
    #         (ssh, sudo, push_path) = ctx.platform.first_start_values

    ctx.flavour.generate_deployment_info(identity_file)
    start(ctx, interactive, execute_test_script, port, push_path)
