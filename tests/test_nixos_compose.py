import pytest
import json

import os.path as op
import shutil

import tempfile

from subprocess import run

from nixos_compose import __version__

FLAKE_LOCK = op.join(op.dirname(__file__), "flake.lock")


@pytest.fixture(scope="function", autouse=True)
def remove_nxc():
    run("rm -rf nxc*", shell=True)


def test_version():
    assert __version__ == "0.1.0"


def test_build():
    with tempfile.TemporaryDirectory() as tmpdirname:
        print("created temporary directory", tmpdirname)
        res = run("nxc init", shell=True, cwd=tmpdirname)
        assert not res.returncode

        res = run("nxc build -n channel:nixos-unstable", shell=True, cwd=tmpdirname)
        assert not res.returncode
        s1 = json.dumps({"built": True, "started": False}, sort_keys=True)
        j1 = json.load(open(f"{tmpdirname}/nxc/state.json"))
        assert s1 == json.dumps(j1)


def test_build_flake():
    # TODO create /tmp/
    with tempfile.TemporaryDirectory() as tmpdirname:
        print("created temporary directory", tmpdirname)
        run("git init", shell=True, cwd=tmpdirname)

        res = run("nxc init --flake ", shell=True, cwd=tmpdirname)
        assert not res.returncode

        shutil.copy2(FLAKE_LOCK, op.join(tmpdirname, "nxc/flake.lock"))
        run("git add nxc", shell=True, cwd=tmpdirname)

        res = run("nxc build -n channel:nixos-unstable", shell=True, cwd=tmpdirname)
        assert not res.returncode
        s1 = json.dumps({"built": True, "started": False}, sort_keys=True)
        j1 = json.load(open(f"{tmpdirname}/nxc/state.json"))
        assert s1 == json.dumps(j1)
