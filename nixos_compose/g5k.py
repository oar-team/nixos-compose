import os
import subprocess
import sys

_ROOT = os.path.abspath(os.path.dirname(__file__))
key_sleep_script = _ROOT + "/tools/g5k_set_pub_key_sleep.sh"


def g5k_get_seed_store(
    ctx, url="http://public.grenoble.grid5000.fr/~orichard/seed-nix-store.tgz"
):
    store_path = f"{os.environ['HOME']}/.local/share/nix/root/nix/store"
    if len(os.listdir(store_path)) == 0:
        subprocess.call(
            f"wget -c {url} -O - | tar -C  ~/.local/share/nix/root -xz", shell=True
        )
    else:
        ctx.elog(f"Store path and direct parent must be empty: {store_path} ")
        sys.exit(1)
