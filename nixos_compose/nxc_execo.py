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
import tempfile
from .context import Context
from .actions import realpath_from_store, translate_hosts2ip
from .flavours.grid5000 import G5kRamdiskFlavour, G5KImageFlavour
from .g5k import key_sleep_script
from .httpd import HTTPDaemon

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
def print_total_size(store_path: str, build_node, location_nix_store, nix_chroot_script="/tmp/nix-user-chroot-companion/nix-user-chroot.sh") -> int:
    """
    Get the store reference of the store provided store path
    """
    dump_path = "/tmp/nix_store.dump"
    nix_store_cmd = f"/bin/bash {nix_chroot_script} store {store_path} {dump_path}"
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

def clean_nix_store(build_node, nix_chroot_script):
    # 1) get and remove all the `execo builds`
    path_gcroots = f"{os.environ['HOME']}/.nix/var/nix/gcroots/auto"
    print(f"gcroots: {path_gcroots}")
    # for link in os.listdir(path_gcroots):
    #     full_link = op.join(path_gcroots, link)
    #     actual_result = os.readlink(full_link)
    #     print(f"Found: {actual_result}")
    #     # if op.basename(actual_result) == "execo_build" and op.exists(actual_result):
    #     if op.exists(actual_result):
    #         print(f"Removing: {actual_result}")
    #         os.remove(actual_result)


    # 2) running nix garbage collect
    clean_store_remote = SshProcess(f"/bin/bash {nix_chroot_script} clean", build_node)
    clean_store_remote.run()
    print(clean_store_remote.stdout)

def get_build_node(site, cluster, extra_job_type, walltime=3600):
    oar_job = oarsub([(OarSubmission(f"{{cluster='{cluster}'}}/nodes=1", walltime, job_type=["allow_classic_ssh"] + extra_job_type), site)])
    job_id, site = oar_job[0]
    wait_oar_job_start(job_id, site)
    build_node = get_oar_job_nodes(job_id, site)[0] # there is only one node
    return (job_id, build_node)

def build_derivation(build_node, nxc_path, flavour, composition_name, nix_chroot_script, clean_store):
    if nix_chroot_script is None:
        # Step 1: git clone the nix-user-chroot-companion ----------------------------------------------
        git_nix_chroot_command = "cd /tmp; /usr/bin/git clone git@github.com:GuilloteauQ/nix-user-chroot-companion.git"
        git_nix_chroot_remote = SshProcess(git_nix_chroot_command, build_node, shell=True)
        git_nix_chroot_remote.run()
        nix_chroot_script = "/tmp/nix-user-chroot-companion/nix-user-chroot.sh"

    nix_chroot_script = realpath_from_store(Context(), nix_chroot_script)

    # Step 2: execute nxc build --------------------------------------------------------------------
    result_path = f"{op.realpath(nxc_path)}/execo_build"

    if clean_store:
        if op.exists(result_path):
            clean_store_remote = SshProcess(f"/bin/bash {nix_chroot_script} delete {result_path}", build_node)
            clean_store_remote.run()
        
        execo_engine.log.logger.info("Starting Garbage Collecting")
        clean_nix_store(build_node, nix_chroot_script)
        execo_engine.log.logger.info("Done Garbage Collecting")

    execo_engine.log.logger.info("Starting Building")
    nxc_build_command = f"/bin/bash {nix_chroot_script} {nxc_path} {composition_name} {flavour} {result_path}"
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
    total_output_size = print_total_size(sym_link_path, build_node, location_nix_store, nix_chroot_script=nix_chroot_script)
    execo_engine.log.logger.info(f"The total size of the output is {total_output_size} bytes")
    return (compose_info_path, end_build_time - start_build_time, total_output_size)


def build_nxc_execo(nxc_path,
                    site,
                    cluster,
                    walltime=3600,
                    flavour="g5k-ramdisk",
                    composition_name="composition",
                    extra_job_type=[],
                    nix_chroot_script=None,
                    clean_store=False):
    """
    Reserves the g5k nodes and build the composition
    returns the path to the compose_info_file
    """
    (job_id, build_node) = get_build_node(site, cluster, extra_job_type, walltime)
    execo_engine.log.logger.info(f"Building on node {build_node.address}")

    infos_build = build_derivation(build_node, nxc_path, flavour, composition_name, nix_chroot_script, clean_store)

    execo_engine.log.logger.info("Now giving back the build node")
    oardel([(job_id, site)])

    #execo_engine.log.logger.info(f"The compose info file is stored at {compose_info_path}")
    return infos_build

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
                          composition_name="composition",
                          roles_quantities={}):
    """
    Brother of the "get_oar_job_nodes" function from execo
    but does the mapping with roles from NXC
    """
    ctx = Context()
    # TODO: kaberk
    ctx.composition_name = composition_name
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

    g5k_nodes = get_oar_job_nodes(oar_job_id, site)
    print(f"G5K nodes: {g5k_nodes}")
    machines = [node.address for node in g5k_nodes]
    if len(machines) > 4:
        ctx.use_http = True
        ctx.httpd = HTTPDaemon(ctx=ctx)
        ctx.httpd.start(directory=ctx.envdir)
    translate_hosts2ip(ctx, machines)

    if flavour_name == "g5k-ramdisk":
        flavour = G5kRamdiskFlavour(ctx)
    elif flavour_name == "g5k-image":
        flavour = G5KImageFlavour(ctx)
    else:
        raise Exception(f"'{flavour_name}' is not an available flavour")
    # ?!
    flavour.ctx.flavour = flavour

    flavour.generate_deployment_info()

    flavour.ctx.mode = {"name": "ssh", "vm": False, "shell": "ssh"}
    # flavour.ctx.ssh = f"OAR_JOB_ID={oar_job_id} oarsh"
    flavour.ctx.ssh = "ssh"
    flavour.ctx.sudo = "sudo-g5k"

    flavour.ctx.log("Launch ssh(s) kexec")
    if hasattr(flavour, "generate_kexec_scripts"):
        flavour.generate_kexec_scripts()
        flavour.launch()
    else:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            machines_str = ""
            for machine in machines:
                machines_str += f"{machine}\n"
            tmp.write(machines_str.encode('utf-8'))
            tmp.flush()
            flavour.launch(machine_file=tmp.name)
        finally:
            tmp.close()
            os.unlink(tmp.name)

    roles = {}
    for ip_addr, node_info in flavour.ctx.deployment_info["deployment"].items():
        node_role = node_info["role"]
        if node_role in roles:
            roles[node_role].append(Host(ip_addr, user="root"))
        else:
            roles[node_role] = [Host(ip_addr, user="root")]

    if ctx.use_httpd:
        ctx.httpd.stop()
    return roles

