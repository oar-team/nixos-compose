from subprocess import run

from nixos_compose import __version__


def test_version():
    print(__version__)
    assert __version__ == "0.1.0"


def test_build(tmp_path):
    print("created temporary directory", tmp_path)
    run("git init", shell=True, cwd=tmp_path)

    res = run("nxc init --flake ", shell=True, cwd=tmp_path)
    assert not res.returncode

    run("git add nxc", shell=True, cwd=tmp_path)

    # res = run("nxc build -C composition::nixos-test", shell=True, cwd=tmp_path)
    res = run("nxc build", shell=True, cwd=tmp_path)
    assert not res.returncode
    # s1 = json.dumps({"built": True, "started": False}, sort_keys=True)
    # j1 = json.load(open(f"{tmp_path}/nxc/state.json"))
    # assert s1 == json.dumps(j1)
