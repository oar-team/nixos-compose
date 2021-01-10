import json
import os
import sys
import subprocess
import time
import shutil
from halo import Halo
from .driver import driver_mode


DRIVER_MODES = {
    "vm-ssh": {"name": "vm-ssh", "vm": True, "shell": "ssh"},
    "vm": {"name": "vm", "vm": True, "shell": "chardev"},
    "default": {"name": "default", "vm": False, "shell": "ssh"},
}


def read_deployment_info(deployment_file="deployment.json"):
    with open(deployment_file, "r") as f:
        deployment_info = json.load(f)
    return deployment_info


def read_deployment_info_str(deployment_file="deployment.json"):
    with open(deployment_file, "r") as f:
        deployment_info_str = f.read()
    return deployment_info_str


def read_test_script(compose_info):
    if "test_script" in compose_info:
        with open(compose_info["test_script"], "r") as f:
            test_script = f.read()
        return test_script
    else:
        return None


def read_compose_info(compose_info_file="result"):
    with open(compose_info_file, "r") as f:
        compose_info = json.load(f)
    return compose_info


def get_hosts_ip(hostsfile):
    host2ip = {}
    hips = []
    for host in open(hostsfile, "r"):
        host = host.rstrip()
        if host and (host not in host2ip):
            ip = socket.gethostbyname_ex("host")[2][0]
            host2ip[host] = ip
            hips.append(ip)


def populate_deployment_vm_by_ip(nodes_info):
    i = 0
    deployment = {}
    ips = []
    for role, v in nodes_info.items():
        ip = "10.0.2.{}".format(15 + i)
        ips.append(ip)
        deployment[ip] = {"role": role, "init": v["init"], "vm_id": i}
        if "qemu_script" in v:
            deployment[ip]["qemu_script"] = v["qemu_script"]
        i = i + 1

    return deployment, ips


def generate_deployment_vm(compose_info, ssh_pub_key_file=None):
    if not compose_info:
        compose_info = read_compose_info()

    if not ssh_pub_key_file:
        ssh_pub_key_file = os.environ["HOME"] + "/.ssh/id_rsa.pub"
    with open(ssh_pub_key_file, "r") as f:
        sshkey_pub = f.read().rstrip()

    deployment, ips = populate_deployment_vm_by_ip(compose_info["nodes"])
    deployment = {
        "ssh_key.pub": sshkey_pub,
        "deployment": deployment,
    }

    if "all" in compose_info:
        deployment["all"] = compose_info["all"]

    # for k in ["all", "flavour"]:
    #    if k in compose_info:
    #        deployment[k] = compose_info[k]

    json_deployment = json.dumps(deployment, indent=2)
    with open("deployment.json", "w") as outfile:
        outfile.write(json_deployment)

    return deployment, ips


def wait_ssh_ports(ctx, ips, halo=True):
    ctx.log("Waiting ssh ports:")
    nb_ips = len(ips)
    nb_ssh_port = 0
    waiting_ssh_ports_cmd = (
        f"nmap -p22 -Pn {' '.join(ips)} -oG - | grep '22/open' | wc -l"
    )
    ctx.vlog(waiting_ssh_ports_cmd)
    if halo:
        spinner = Halo(text=f"Opened ssh ports 0/{nb_ips}", spinner="dots")
        spinner.start()
    while nb_ssh_port != nb_ips:
        output = subprocess.check_output(waiting_ssh_ports_cmd, shell=True)
        nb_ssh_port = int(output.rstrip().decode())
        if halo:
            spinner.text = f"Opened ssh ports: {nb_ssh_port}/{nb_ips}"
        time.sleep(0.25)
    if halo:
        spinner.succeed("All ssh ports are opened")
    else:
        ctx.log("All ssh ports are opened")


def copy_result_from_store(store_copy_dir, compose_info=None):
    if not compose_info:
        compose_info = read_compose_info()

    new_compose_info = compose_info.copy()

    if "all" in compose_info:
        for target in ["kernel", "initrd", "qemu_script"]:
            new_target = store_copy_dir + "/" + target
            shutil.copy(compose_info["all"][target], new_target)
            new_compose_info["all"][target] = new_target
    else:
        for r, v in compose_info["nodes"].items():
            for target in ["kernel", "initrd", "qemu_script"]:
                new_target = store_copy_dir + "/" + "_" + r
                shutil.copy(v[target], new_target)
                new_compose_info["nodes"][target] = new_target

    if "test_script" in compose_info:
        new_target = store_copy_dir + "/test_script"
        shutil.copy(compose_info["test_script"], new_target)
        new_compose_info["test_script"] = new_target

    # save new updated compose_indo
    json_new_compose_info = json.dumps(new_compose_info, indent=2)
    with open("compose_info.json", "w") as outfile:
        outfile.write(json_new_compose_info)


def connect(ctx, user, hostname):
    deployment_info = read_deployment_info()
    role = hostname
    for ip, v in deployment_info["deployment"].items():
        if v["role"] == role:
            hostname = ip
            break
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR -l {user} {hostname}"
    return_code = subprocess.run(ssh_cmd, shell=True).returncode
    if return_code:
        ctx.wlog(f"SSH exit code is not null: {return_code}")
    sys.exit(return_code)


# TODO launch_vm(ctx, kexec_info, debug=False):
# TODO launch_vm_deploy(ctx, deployment, httpd_port=0, debug=False):
def launch_vm(ctx, deployment, httpd_port=0, debug=False):

    if not os.path.exists("/tmp/kexec-qemu-vde1.ctl/ctl"):
        ctx.log("need sudo to create tap0 interface")
        subprocess.call("sudo true", shell=True)

    for ip, v in deployment["deployment"].items():
        qemu_script = v["qemu_script"]
        # cmd_qemu_script = f"DEPLOY='deploy=http://10.0.2.1:{httpd_port}/deployment.json' TAP=1"
        #
        cmd_qemu_script = "TAP=1"
        if httpd_port:
            cmd_qemu_script = " DEPLOY=1"
        if debug:
            cmd_qemu_script += " DEBUG_INITRD=boot.debug1mounts"

        cmd_qemu_script += " VM_ID={:02d} {} &".format(v["vm_id"], qemu_script)
        ctx.log("launch: {}".format(v["role"]))
        ctx.vlog(f"command: {cmd_qemu_script}")
        # import pdb; pdb.set_trace()
        # subprocess.Popen(
        #    cmd_qemu_script,
        #    stdin=subprocess.DEVNULL,
        # stdout=subprocess.STDOUT,
        # stderr=subprocess.STDOUT,
        #    shell=True,
        # cwd=self.state_dir,
        # env=environment,
        # )
        # subprocess.call(cmd_qemu_script, shell=True)
        # time.sleep(110)


def launch_driver_vm(
    ctx, deployment, flavour, ips, httpd_port=0, driver_repl=False, test_script=None
):
    driver_mode(DRIVER_MODES["vm"], flavour, deployment, driver_repl, test_script)
    # driver_vm(deployment, ips, test_script)
