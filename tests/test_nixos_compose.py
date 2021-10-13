import json

from subprocess import run

from nixos_compose import __version__


def run_test(cmd, tmp_path, ret_test=1):
    res = run(cmd, shell=True, cwd=tmp_path)
    if ret_test:
        print(f"cmd: {cmd} returncode: {res.returncode}")
        assert not res.returncode
    return res


def run_init(cmd_init, tmp_path, ret_test=1):
    run_test("git init -b main", tmp_path)
    res = run_test(cmd_init, tmp_path, ret_test)
    run_test("git add nxc", tmp_path)
    return res


def test_version():
    print(__version__)
    assert __version__ == "0.1.0"


def test_build(tmp_path):
    print("created temporary directory", tmp_path)

    run_init("nxc init", tmp_path)

    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build", tmp_path)

    # s1 = json.dumps({"built": True, "started": False}, sort_keys=True)
    # j1 = json.load(open(f"{tmp_path}/nxc/state.json"))
    # assert s1 == json.dumps(j1)


def test_build_nur(tmp_path):
    print("created temporary directory", tmp_path)

    run_init("nxc init --nur", tmp_path)

    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build", tmp_path)


def test_build_multi_compositions(tmp_path):
    print("created temporary directory", tmp_path)

    run_init("nxc init -e multi-compositions", tmp_path)

    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build -C bar::nixos-test", tmp_path)


def test_start_docker(tmp_path):
    print("created temporary directory", tmp_path)

    run_init("nxc init", tmp_path)

    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build -f docker", tmp_path)

    run_test("nxc start", tmp_path)

    f = open(f"{tmp_path}/nxc/deploy/composition::docker.json", "r")
    docker_compose_file = json.load(f)["docker-compose-file"]
    print("cleaning docker")
    run_test(f"docker-compose -f {docker_compose_file} down", tmp_path)
