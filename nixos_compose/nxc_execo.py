from execo import Host
from execo_g5k import get_oar_job_nodes

import os
import os.path as op

import tempfile
from .context import Context
from .actions import realpath_from_store, translate_hosts2ip
from .flavours import get_flavour_by_name

# from .g5k import key_sleep_script
from .httpd import HTTPDaemon


def get_envdir(ctx):
    if os.path.isfile("nxc.json"):
        if os.path.islink("nxc.json"):
            ctx.nxc_file = os.readlink("nxc.json")
        else:
            ctx.nxc_file = op.abspath("nxc.json")
        with open(ctx.nxc_file, "r") as f:
            ctx.load_nxc(f)

        ctx.envdir = op.dirname(ctx.nxc_file)
    else:
        raise Exception("Cannot find `nxc.json`")


def get_oar_job_nodes_nxc(
    oar_job_id,
    site,
    compose_info_file=None,
    flavour_name="g5k-nfs-store",
    composition_name="composition",
    roles_quantities={},
    port=0,
):
    """
    Brother of the "get_oar_job_nodes" function from execo
    but does the mapping with roles from NXC
    """
    ctx = Context()
    # TODO: kaberk
    ctx.composition_name = composition_name
    ctx.flavour_name = flavour_name
    ctx.composition_flavour_prefix = f"{composition_name}::{flavour_name}"
    ctx.roles_distribution = roles_quantities

    ctx.envdir = None
    get_envdir(ctx)

    if compose_info_file:
        ctx.compose_info_file = compose_info_file
    else:
        build_folder = op.join(ctx.envdir, "build")
        simlink_build = op.join(
            build_folder, f"{ctx.composition_name}::{ctx.flavour_name}"
        )
        ctx.compose_info_file = realpath_from_store(ctx, simlink_build)

    flavour = get_flavour_by_name(flavour_name)(ctx)
    ctx.flavour = flavour

    # print(f"compose info file: {ctx.compose_info_file}")

    g5k_nodes = get_oar_job_nodes(oar_job_id, site)
    print(f"G5K nodes: {g5k_nodes}")
    machines = [node.address for node in g5k_nodes]
    if len(machines) > 4:
        ctx.use_http = True
        ctx.httpd = HTTPDaemon(ctx=ctx, port=port)
        ctx.httpd.start(directory=ctx.envdir)
    translate_hosts2ip(ctx, machines)

    flavour.generate_deployment_info()

    ctx.log("Deploying")
    if hasattr(flavour, "generate_kexec_scripts"):
        flavour.generate_kexec_scripts()
        flavour.launch()
    else:
        user = os.environ["USER"]
        tempfile.tempdir = f"/home/{user}/public"
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_kaenv = tempfile.NamedTemporaryFile(delete=False)
        temp_dir = tempfile.TemporaryDirectory()
        try:
            machines_str = "\n".join(machine for machine in machines)
            # for machine in machines:
            #     machines_str += f"{machine}\n"
            tmp.write(machines_str.encode("utf-8"))
            tmp.flush()
            nxc_image_path = op.join(temp_dir.name, "nixos.tar.xz")
            flavour.launch(
                machine_file=tmp.name,
                kaenv_path=tmp_kaenv.name,
                deploy_image_path=nxc_image_path,
            )
        finally:
            tmp.close()
            os.unlink(tmp.name)
            tmp_kaenv.close()
            os.unlink(tmp_kaenv.name)
            temp_dir.cleanup()

    roles = {}
    nodes = {}
    for ip_addr, node_info in flavour.ctx.deployment_info["deployment"].items():
        node_role = node_info["role"]
        localhost = Host(ip_addr, user="root")
        nodes[node_info["host"]] = localhost
        if node_role in roles:
            roles[node_role].append(localhost)
        else:
            roles[node_role] = [localhost]

    if ctx.use_httpd:
        ctx.httpd.stop()
    return (nodes, roles)
