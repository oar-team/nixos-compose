import json
import os
import os.path as op
import socket
import sys
import subprocess
import time
import shutil
import base64
import click
from halo import Halo

# from .driver import driver_mode


DRIVER_MODES = {
    "vm-ssh": {"name": "vm-ssh", "vm": True, "shell": "ssh"},
    "vm": {"name": "vm", "vm": True, "shell": "chardev"},
    "remote": {"name": "ssh", "vm": False, "shell": "ssh"},
}


##
# Generate/manipulate/copy deploy, compose files
#
def read_deployment_info(ctx, deployment_file="deployment.json"):
    with open(op.join(ctx.envdir, deployment_file), "r") as f:
        deployment_info = json.load(f)

    ctx.deployment_info = deployment_info
    return


def read_deployment_info_str(ctx, deployment_file="deployment.json"):
    with open(op.join(ctx.envdir, deployment_file), "r") as f:
        deployment_info_str = f.read()
    return deployment_info_str


def read_test_script(compose_info_or_str):
    if isinstance(compose_info_or_str, str):
        filename = compose_info_or_str
    elif "test_script" in compose_info_or_str:
        filename = compose_info_or_str["test_script"]
    else:
        return None
    with open(filename, "r") as f:
        test_script = f.read()
        return test_script


def read_compose_info(ctx, compose_info_filename="result"):
    compose_info_file = op.join(ctx.envdir, compose_info_filename)
    if compose_info_filename == "result" and not op.isfile(compose_info_file):
        compose_info_file = op.join(ctx.envdir, "compose_info.json")
        if not op.isfile(compose_info_file):
            raise click.ClickException(
                f"{compose_info_filename} does not exist neither compose_info.json"
            )

    with open(compose_info_file, "r") as f:
        compose_info = json.load(f)

    if "flavour" in compose_info:
        ctx.flavour = compose_info["flavour"]

    ctx.compose_info = compose_info
    return


def get_hosts_ip(ctx, hostsfile):
    for host in open(hostsfile, "r"):
        host = host.rstrip()
        if host and (host not in ctx.host2ip_address):
            ip = socket.gethostbyname_ex(host)[2][0]
            ctx.host2ip_address[host] = ip
            ctx.ip_addresses.append(ip)
    return


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


def populate_deployment_ips(nodes_info, ips):
    i = 0
    deployment = {}
    for role, v in nodes_info.items():
        ip = ips[i]
        deployment[ip] = {"role": role, "init": v["init"]}
        i = i + 1

    return deployment


def generate_deployment_info(ctx, ssh_pub_key_file=None):
    if not ctx.compose_info:
        read_compose_info(ctx)

    if not ssh_pub_key_file:
        ssh_pub_key_file = os.environ["HOME"] + "/.ssh/id_rsa.pub"
    with open(ssh_pub_key_file, "r") as f:
        sshkey_pub = f.read().rstrip()

    if ctx.ip_addresses:
        deployment = populate_deployment_ips(
            ctx.compose_info["nodes"], ctx.ip_addresses
        )
    else:
        deployment, ctx.ip_addresses = populate_deployment_vm_by_ip(
            ctx.compose_info["nodes"]
        )
    deployment = {
        "ssh_key.pub": sshkey_pub,
        "deployment": deployment,
    }

    if "all" in ctx.compose_info:
        deployment["all"] = ctx.compose_info["all"]

    # for k in ["all", "flavour"]:
    #    if k in compose_info:
    #        deployment[k] = compose_info[k]

    json_deployment = json.dumps(deployment, indent=2)
    with open(op.join(ctx.envdir, "deployment.json"), "w") as outfile:
        outfile.write(json_deployment)

    ctx.deployment_info = deployment
    return


def generate_kexec_scripts(ctx):
    # deploy = "deploy=http://172.16.31.101:8000/deployment.json"
    generate_deploy_info_b64(ctx)
    deployinfo_b64 = ctx.deployment_info_b64
    kexec_scripts_path = os.path.join(ctx.envdir, "kexec_scripts")
    os.makedirs(kexec_scripts_path, mode=0o700, exist_ok=True)

    if "all" in ctx.deployment_info:
        kernel_path = f"{ctx.envdir}/kernel"
        initrd_path = f"{ctx.envdir}/initrd"
        kexec_args = f"-l {kernel_path} --initrd={initrd_path} "
        kexec_args += (
            f"--append='deploy:{deployinfo_b64} console=tty0 console=ttyS0,115200'"
        )
        script_path = os.path.join(kexec_scripts_path, "kexec.sh")
        with open(script_path, "w") as kexec_script:
            kexec_script.write("#!/usr/bin/env bash\n")
            kexec_script.write(": ''${SUDO:=sudo}\n")
            kexec_script.write(f"$SUDO kexec {kexec_args}\n")
            kexec_script.write("$SUDO kexec -e\n")
        os.chmod(script_path, 0o755)
    else:
        for ip, v in ctx.deployment_info["deployment"].items():
            role = v["role"]
            kernel_path = f"{ctx.envdir}/kernel_{role}"
            initrd_path = f"{ctx.envdir}/initrd_{role}"
            init_path = v["init"]
            kexec_args = f"-l {kernel_path} --initrd={initrd_path} "
            kexec_args += f"--append='init={init_path} deploy:{deployinfo_b64} console=tty0 console=ttyS0,115200'"
            script_path = os.path.join(kexec_scripts_path, f"kexec_{role}.sh")
            with open(script_path, "w") as kexec_script:
                kexec_script.write("#!/usr/bin/env bash\n")
                kexec_script.write(": ''${SUDO:=sudo}\n")
                kexec_script.write(f"$SUDO kexec {kexec_args}\n")
                kexec_script.write("$SUDO kexec -e\n")

            os.chmod(script_path, 0o755)


def generate_deploy_info_b64(ctx):
    deployment_info_str = json.dumps(ctx.deployment_info)
    ctx.deployment_info_b64 = base64.b64encode(deployment_info_str.encode()).decode()

    if len(ctx.deployment_info_b64) > (4096 - 256):
        ctx.log(
            "The base64 encoded deploy data is too large: use an http server to serve it"
        )
        sys.exit(1)
    return


def copy_result_from_store(ctx, compose_info=None):
    store_copy_dir = ctx.envdir
    if not compose_info:
        compose_info = read_compose_info(ctx)

    new_compose_info = compose_info.copy()

    if "all" in compose_info:
        for target in ["kernel", "initrd", "qemu_script"]:
            new_target = op.join(store_copy_dir, target)
            shutil.copy(compose_info["all"][target], new_target)
            new_compose_info["all"][target] = new_target
    else:
        for r, v in compose_info["nodes"].items():
            for target in ["kernel", "initrd", "qemu_script"]:
                new_target = op.join(store_copy_dir, target + "_" + r)
                shutil.copy(v[target], new_target)
                new_compose_info["nodes"][target] = new_target

    if "test_script" in compose_info:
        new_target = op.join(store_copy_dir, "test_script")
        shutil.copy(compose_info["test_script"], new_target)
        new_compose_info["test_script"] = new_target

    # save new updated compose_info
    json_new_compose_info = json.dumps(new_compose_info, indent=2)
    with open(op.join(store_copy_dir, "compose_info.json"), "w") as outfile:
        outfile.write(json_new_compose_info)


##
#  Operation: connect, launch, wait_ssh_port,
#


def launch_ssh_kexec(ctx, ip=None):
    if "all" in ctx.deployment_info:
        kexec_script = op.join(ctx.envdir, "kexec_scripts/kexec.sh")
        if ctx.sudo:
            sudo = f"SUDO={ctx.sudo} "
        else:
            sudo = ""

        def one_ssh_kexec(ip_addr):
            ssh_cmd = (
                f'{ctx.ssh} {ip_addr} "screen -dm bash -c \\"{sudo}{kexec_script}\\""'
            )
            subprocess.call(ssh_cmd, shell=True)

        if ip:
            one_ssh_kexec(ip)
        else:
            for ip in ctx.deployment_info["deployment"].keys():
                one_ssh_kexec(ip)
    else:
        raise Exception("Sorry, only all in one image version support up to now")


def wait_ssh_ports(ctx, ips=None, halo=True):
    ctx.log("Waiting ssh ports:")
    if not ips:
        ips = ctx.ip_addresses
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


def connect(ctx, user, host):
    if not ctx.deployment_info:
        read_deployment_info(ctx)

    role = host
    for ip, v in ctx.deployment_info["deployment"].items():
        if v["role"] == role:
            host = ip
            break
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR -l {user} {host}"
    return_code = subprocess.run(ssh_cmd, shell=True).returncode
    if return_code:
        ctx.wlog(f"SSH exit code is not null: {return_code}")
    sys.exit(return_code)


def connect_tmux(ctx, user, hosts=None, window_name="nxc"):

    if not hosts:
        hosts = ctx.deployment_info["deployment"].keys()
    ssh_cmds = [
        f"ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR -l {user} {h}"
        for h in hosts
    ]

    if "TMUX" not in os.environ:
        cmd = "tmux new  -d"
        subprocess.call(cmd, shell=True)

    cmd = f"tmux new-window -n {window_name} -d"
    subprocess.call(cmd, shell=True)

    cmd = f'tmux splitw -h -p 50 -t {window_name}.0 "{ssh_cmds[0]}"'
    subprocess.call(cmd, shell=True)

    num_panes = len(hosts) - 1

    for i, ssh_cmd in enumerate(ssh_cmds[1:]):
        ratio = round(100 * (1 - (1.0 / (1 + num_panes - i))))
        cmd = f'tmux splitw -v -p {ratio} -t {window_name}.{i+1} "{ssh_cmd}"'
        subprocess.call(cmd, shell=True)

    cmd = f"tmux select-pane -t {window_name}.0"
    subprocess.call(cmd, shell=True)

    cmd = f"tmux select-window -t  {window_name}"
    subprocess.call(cmd, shell=True)

    if "TMUX" not in os.environ:
        cmd = "tmux attach"
        subprocess.call(cmd, shell=True)


# TODO launch_vm(ctx, kexec_info, debug=False):
# TODO launch_vm_deploy(ctx, deployment, httpd_port=0, debug=False):
def launch_vm(ctx, httpd_port=0, debug=False):

    if not os.path.exists("/tmp/kexec-qemu-vde1.ctl/ctl"):
        ctx.log("need sudo to create tap0 interface")
        subprocess.call("sudo true", shell=True)

    for ip, v in ctx.deployment_info["deployment"].items():
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


# def launch_driver_vm(
#     ctx, deployment, flavour, ips, httpd_port=0, driver_repl=False, test_script=None
# ):
#     driver_mode(DRIVER_MODES["vm"], flavour, deployment, driver_repl, test_script)
#     # driver_vm(deployment, ips, test_script)

# def launch_driver_ssh(
#         ctx, deployment, flavour, ips, httpd_port, driver_repl, test_script, ssh, sudo
# ):
#     driver_mode(DRIVER_MODES["remote"], flavour, deployment, driver_repl, test_script)
