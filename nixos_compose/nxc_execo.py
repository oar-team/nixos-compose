import execo
import execo_g5k
import execo_engine
from execo import Process, Host, Remote, SshProcess, Report
from execo_g5k import get_oar_job_nodes, oarsub, oardel, OarSubmission, wait_oar_job_start
from execo_engine import Engine
import os
import os.path as op
import time
import logging
from .context import Context
from .actions import realpath_from_store, translate_hosts2ip
from .flavours.grid5000 import G5kRamdiskFlavour

# Stolen from Adrien Faure: github.com:adfaure/vinix.git
def get_size(start_path: str):
    """Get the size of the folder `start_path`"""
    total_size = 0
    for dirpath, _, filenames in os.walk(start_path):
        for f in filenames:
            file_path = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)

    return total_size

# Stolen from Adrien Faure: github.com:adfaure/vinix.git
def print_total_size(store_path: str, build_node, location_nix_store) -> int:
    """
    Get the store reference of the store provided store path
    """
    dump_path = "/tmp/nix_store.dump"
    nix_store_cmd = f"/bin/bash /tmp/nix-user-chroot-companion/nix-user-chroot.sh store {store_path} {dump_path}"
    nix_store_remote = SshProcess(nix_store_cmd, build_node, shell=True)
    nix_store_remote.run()

    read_dump_remote = SshProcess(f"cat {dump_path}", build_node)
    read_dump_remote.run()
    output = read_dump_remote.stdout
    # print(output)

    total_size = 0
    # for path in output.decode().splitlines():
    for path in output.splitlines():
        real_path = path.replace("/nix/store", location_nix_store)
        total_size += get_size(real_path)

    return total_size

def build_nxc_execo(nxc_path, site, cluster, walltime=3600, flavour="g5k-ramdisk", extra_job_type=[]):
    """
    Reserves the g5k nodes and build the composition
    returns the path to the compose_info_file
    """
    oar_job = oarsub([(OarSubmission(f"{{cluster='{cluster}'}}/nodes=1", walltime, job_type=["allow_classic_ssh"] + extra_job_type), site)])
    job_id, site = oar_job[0]
    wait_oar_job_start(job_id, site)
    build_node = get_oar_job_nodes(job_id, site)[0] # there is only one node
    execo_engine.log.logger.info(f"Building on node {build_node.address}")

    # Step 1: git clone the nix-user-chroot-companion ----------------------------------------------
    git_nix_chroot_command = "cd /tmp; /usr/bin/git clone git@github.com:GuilloteauQ/nix-user-chroot-companion.git"
    git_nix_chroot_remote = SshProcess(git_nix_chroot_command, build_node, shell=True)
    git_nix_chroot_remote.run()
    # Step 2: execute nxc build --------------------------------------------------------------------
    result_path = f"{op.realpath(nxc_path)}/execo_build"
    nxc_build_command = f"/bin/bash /tmp/nix-user-chroot-companion/nix-user-chroot.sh {nxc_path} {flavour} {result_path}"
    nxc_build_remote = SshProcess(nxc_build_command, build_node, shell=True)
    start_build_time = time.time()
    nxc_build_remote.run()
    end_build_time = time.time()

    execo_engine.log.logger.info(f"Done building. Composition built in {end_build_time - start_build_time} seconds")

    user = os.environ["USER"]
    location_nix_store = f"/home/{user}/.nix/store"
    sym_link_path = str(op.realpath(op.join(nxc_path, result_path)))
    compose_info_path = sym_link_path.replace("/nix/store", location_nix_store)

    execo_engine.log.logger.info("Now checking the size of the output")
    # total_output_size = print_total_size(compose_info_path, build_node, location_nix_store)
    total_output_size = print_total_size(sym_link_path, build_node, location_nix_store)
    execo_engine.log.logger.info(f"The total size of the output is {total_output_size} bytes")

    execo_engine.log.logger.info("Now giving back the build node")
    oardel([(job_id, site)])

    execo_engine.log.logger.info(f"The compose info file is stored at {compose_info_path}")
    return (compose_info_path, end_build_time - start_build_time, total_output_size)

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

def get_oar_job_nodes_nxc(oar_job_id,
                          site,
                          compose_info_file=None,
                          flavour_name="g5k-ramdisk",
                          roles_quantities={}):
    """
    Brother of the "get_oar_job_nodes" function from execo
    but does the mapping with roles from NXC
    """
    ctx = Context()
    # TODO: kaberk
    ctx.composition_name = "composition"
    ctx.flavour_name = flavour_name
    ctx.set_roles_quantities(roles_quantities)

    ctx.envdir = None
    get_envdir(ctx)

    if compose_info_file:
        ctx.compose_info_file = compose_info_file
    else:
        build_folder = op.join(ctx.envdir, "build")
        simlink_build = op.join(build_folder, f"{ctx.composition_name}::{ctx.flavour_name}")
        ctx.compose_info_file = realpath_from_store(ctx, simlink_build)

    print(f"compose info file: {ctx.compose_info_file}")

    flavour = G5kRamdiskFlavour(ctx)
    # ?!
    flavour.ctx.flavour = flavour

    g5k_nodes = get_oar_job_nodes(oar_job_id, site)
    print(f"G5K nodes: {g5k_nodes}")
    machines = [node.address for node in g5k_nodes]
    translate_hosts2ip(ctx, machines)
    flavour.generate_deployment_info()

    flavour.ctx.mode = {"name": "ssh", "vm": False, "shell": "ssh"}
    # flavour.ctx.ssh = f"OAR_JOB_ID={oar_job_id} oarsh"
    flavour.ctx.ssh = "ssh"
    flavour.ctx.sudo = "sudo-g5k"
    flavour.generate_kexec_scripts()

    flavour.ctx.log("Launch ssh(s) kexec")
    flavour.launch()

    roles = {}
    for ip_addr, node_info in flavour.ctx.deployment_info["deployment"].items():
        node_role = node_info["role"]
        if node_role in roles:
            roles[node_role].append(Host(ip_addr, user="root"))
        else:
            roles[node_role] = [Host(ip_addr, user="root")]
    return roles

