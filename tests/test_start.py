from subprocess import run


def run_test(cmd, tmp_path, ret_test=1):
    res = run(cmd, shell=True, cwd=tmp_path)
    if ret_test:
        print(f"cmd: {cmd} returncode: {res.returncode}")
        assert not res.returncode
    return res


def run_init(cmd_init, tmp_path, ret_test=1):
    run_test("git init", tmp_path)
    res = run_test(cmd_init, tmp_path, ret_test)
    run_test("git add .", tmp_path)
    return res


def test_start_docker(tmp_path):
    run_init("nxc init", tmp_path)

    # run_test("nxc build -C composition::nixos-test", tmp_path)
    run_test("nxc build -f docker", tmp_path)

    run_test("nxc start -t", tmp_path)
    run_test("nxc start -t -C composition::docker", tmp_path)


def test_start_vm_ramdisk(tmp_path):
    run_init("nxc init", tmp_path)
    run_test("nxc build -f vm-ramdisk", tmp_path)
    run_test("nxc start -t", tmp_path)
