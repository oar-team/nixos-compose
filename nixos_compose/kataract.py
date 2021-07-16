#!/usr/bin/env python3
import sys
import argparse
import asyncio
from string import Template

CMD_BASE = Template(
    r'echo "s=\$$(mktemp); echo \\"$inner_cmd\\" > \$$s; nohup bash \$$s > /dev/null 2> /dev/null < /dev/null &" | $ssh $host "bash -s"'
)

CMD_START = Template(
    "until nc -z $host $port1 ; do sleep 0.01; done; base64 $file_input  >/dev/tcp/$host/$port0"
)
CMD_END = Template("nc -l $port0 | base64 -d > $file_output & nc -l $port1")
CMD_TEE = Template(
    "until nc -z $host $port3; do sleep 0.01; done; nc -l $port0 | tee >(cat > /dev/tcp/$host/$port2) | base64 -d > $file_output & nc -l $port1"
)

# B  = cmd_base.substitute({'inner_cmd' : 'until nc -z localhost 5556; do sleep 0.01; done; nc -l 4444 | tee >(cat > /dev/tcp/127.0.0.1/5555) | base64 -d > /tmp/yopB & nc -l 4446'})

# A = 'until nc -z localhost 4446; do sleep 0.01; done; base64 /tmp/vm-state-client1/client1.qcow2  >/dev/tcp/127.0.0.1/4444'


def elog(msg, *args):
    print("\033[91mError:\033[0m", *args, file=sys.stderr)


def vlog(msg, *args):
    print(*args)


async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        executable="/bin/bash",
    )

    stdout, stderr = await proc.communicate()

    return (proc.returncode, stdout, stderr)


def generate_pipe_tasks(
    hosts, file_input, file_output, port0="5555", port1="5556", ssh="ssh"
):
    hosts_rev = hosts.copy()
    hosts_rev.reverse()

    def cmd_tee(h, h_next):
        # print(h, h_next)
        cmd_tee = CMD_TEE.substitute(
            {
                "host": h_next,
                "port1": port1,
                "port0": port0,
                "port3": port1,
                "port2": port0,
                "file_output": file_output,
            }
        )
        return CMD_BASE.substitute({"inner_cmd": cmd_tee, "ssh": ssh, "host": h})

    tees = [cmd_tee(h, hosts_rev[i]) for i, h in enumerate(hosts_rev[1:])]

    cmd_end = CMD_END.substitute(
        {"port1": port1, "port0": port0, "file_output": file_output}
    )
    end = CMD_BASE.substitute({"inner_cmd": cmd_end, "ssh": ssh, "host": hosts_rev[0]})

    start = CMD_START.substitute(
        {"host": hosts[0], "port1": port1, "port0": port0, "file_input": file_input}
    )

    tasks_cmd = [end] + tees + [start]

    # for c in tasks_cmd:
    #    print(c)
    #    print("")

    return tasks_cmd


def generate_scp_tasks(hosts, file_input, file_output, scp="scp", user=""):
    if user:
        user = f"{user}@"
    tasks_cmd = [f"{scp} {file_input} {user}{h}:{file_output}" for h in hosts]
    # print(tasks_cmd)
    return tasks_cmd


def exec_kataract_tasks(tasks_cmd, elog=elog, vlog=vlog):

    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()

    tasks = [run(task_cmd) for task_cmd in tasks_cmd]

    finished, unfinished = loop.run_until_complete(asyncio.wait(tasks, timeout=60))

    if len(unfinished) > 0:
        elog("Failed")

    vlog(f"unfinished: {len(unfinished)}")
    vlog(f"finished: {len(finished)}")

    for task in finished:
        r = task.result()
        if r[0] != 0 or r[2]:
            vlog(f"{r}")
    loop.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="kataract",
        description="File broadcaster based on TCP Pipeline. Pipeline is initiated by bash command sent through ssh connection",
    )
    parser.add_argument(
        "--input", "-i", dest="file_input", required=True, help="input file to send"
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="file_output",
        required=True,
        help="output file to write on receiver hosts",
    )
    parser.add_argument(
        "--ssh",
        "-s",
        dest="ssh",
        default="ssh",
        help="ssh command to use to reach host, 'ssh' by default",
    )
    parser.add_argument(
        "-m", dest="hosts", action="append", required=True, help="receiver hosts"
    )
    parser.add_argument(
        "--port-data",
        "-p",
        dest="port_data",
        default=5555,
        type=int,
        help="port to send data",
    )
    parser.add_argument(
        "--port-ready",
        "-r",
        dest="port_ready",
        default=5556,
        type=int,
        help="port to test if host is ready to receive.",
    )
    parser.add_argument(
        "--scp", "-S", dest="scp", action="store_true", help="use scp to send file."
    )

    # main()
    args = parser.parse_args()

    # if not args.file_input()
    if not args.scp:
        tasks_cmd = generate_pipe_tasks(
            args.hosts,
            args.file_input,
            args.file_output,
            port0=args.port_data,
            port1=args.port_ready,
            ssh=args.ssh,
        )
    else:
        tasks_cmd = generate_scp_tasks(
            args.hosts, args.file_input, args.file_output, scp="scp"
        )

    exec_kataract_tasks(tasks_cmd)
