from subprocess import run

import pkg_resources


def run_test(cmd, tmp_path, ret_test=1):
    res = run(cmd, shell=True, cwd=tmp_path)
    if ret_test:
        print(f"cmd: {cmd} returncode: {res.returncode}")
        assert not res.returncode
    return res


def run_init(cmd_init, tmp_path, ret_test=1):
    # run_test("git init", tmp_path)
    res = run_test(cmd_init, tmp_path, ret_test)
    # run_test("git add .", tmp_path)
    return res


def test_version():
    version = pkg_resources.get_distribution("nixos-compose").version
    print(version)
    assert version == "0.2.0"


def test_build(tmp_path):
    run_init("nxc init", tmp_path)
    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build", tmp_path)
    # s1 = json.dumps({"built": True, "started": False}, sort_keys=True)
    # j1 = json.load(open(f"{tmp_path}/nxc/state.json"))
    # assert s1 == json.dumps(j1)


def test_build_nur(tmp_path):
    run_init("nxc init -t basic-nur", tmp_path)
    run_test("nxc build", tmp_path)


def test_build_multi_compositions(tmp_path):
    run_init("nxc init -t multi-compositions", tmp_path)

    # run_test("nxc build", tmp_path) # TODEBUG
    run_test("nxc build -C bar::nixos-test", tmp_path)
    run_test("nxc build -C foo::nixos-test", tmp_path)


def test_build_kernel_5_4(tmp_path):
    run_init("nxc init -t kernel", tmp_path)
    run_test("nxc build -C linux_5_4::nixos-test", tmp_path)


def test_build_vm_ramdisk(tmp_path):
    run_init("nxc init", tmp_path)
    run_test("nxc build -f vm-ramdisk", tmp_path)
