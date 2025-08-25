export JUST_DIR := justfile_directory()
export NXC_BRANCH := `basename $PWD`

# nxc command from local source version

nxc_local := "nix develop --override-input nxc path:" + justfile_directory() + " -c nxc"
nix_flags := "--nix-flags \"--override-input nxc path:" + justfile_directory() + "\""

#examples:= `cd examples && ls -I "*.*"`

DEFAULT_BASIC_EXAMPLES := "basic basic-nur execo scripts setup webserver"
DEFAULT_COMMON_EXAMPLES := "basic basic-nur execo multi-compositions nbp-mpi nixos-cluster scripts setup shared-directories-users webserver"
DEFAULT_DOCKER_EXAMPLES := DEFAULT_BASIC_EXAMPLES

#DEFAULT_VM_EXAMPLES := DEFAULT_COMMON_EXAMPLES + " kernel"

DEFAULT_VM_EXAMPLES := DEFAULT_BASIC_EXAMPLES
DEFAULT_G5K_EXAMPLES := DEFAULT_COMMON_EXAMPLES + " kernel"
DEFAULT_G5K_SITE := "grenoble"
export TEST_TMP_DIR := `echo $HOME` + "/nxc-test-tmp"
DEFAULT_NBNODES := "1"
DEFAULT_WALLTIME := "1:0"
DEFAULT_EXAMPLE := "basic"

alias b := build
alias dev-p18 := develop-with-poetry-1_8-shell
alias d := develop-venv
alias p := poetry

default:
    @just --list

_copy-prepare-example TMPDIR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    cp -a examples/{{ EXAMPLE }}/* {{ TMPDIR }}
    cd {{ TMPDIR }}
    git init && git add *

build-and-test FLAVOUR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    mkdir -p $TEST_TMP_DIR/{{ FLAVOUR }}
    tmpdir=$(mktemp -d $TEST_TMP_DIR/{{ FLAVOUR }}/{{ EXAMPLE }}.XXXXXX)
    #prepare directory
    just _copy-prepare-example $tmpdir {{ EXAMPLE }}
    cd $tmpdir
    if [[ $(hostname -d) == *"grid5000"* ]] ; then
      shopt -s expand_aliases && alias nxc_local="nxc"
    else
      shopt -s expand_aliases && alias nxc_local="{{ nxc_local }}"
    fi
    nxc_local build {{ nix_flags }} -f {{ FLAVOUR }}
    if [[ {{ FLAVOUR }} == "vm" ]]; then
      # nxc_local start -t # TOFIX
      nxc_local start &
      sleep 20
      nxc_local driver -t
      pkill qemu-system
    else
      nxc_local start
      nxc_local driver -t
      nxc_local stop
    fi

build FLAVOUR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    mkdir -p $HOME/nxc-test-tmp/{{ FLAVOUR }}
    tmpdir=$(mktemp -d $TEST_TMP_DIR/{{ FLAVOUR }}/{{ EXAMPLE }}.XXXXXX)
    #prepare directory
    just _copy-prepare-example $tmpdir {{ EXAMPLE }}
    cd $tmpdir
    if [[ $(hostname -d) == *"grid5000"* ]] ; then
      shopt -s expand_aliases && alias nxc_local="nxc"
    else
      shopt -s expand_aliases && alias nxc_local="{{ nxc_local }}"
    fi
    nxc_local build {{ nix_flags }} -f {{ FLAVOUR }}

docker EXAMPLE="basic":
    just build-and-test docker {{ EXAMPLE }}

vm EXAMPLE="basic":
    just build-and-test vm {{ EXAMPLE }}

list-examples:
    #!/usr/bin/env bash
    cd $JUST_DIR/examples
    for example in `ls -I "*.*"`; do echo "$example"; echo poy; done

_examples-test FLAVOUR +EXAMPLES:
    #!/usr/bin/env bash
    for example in {{ EXAMPLES }} ; do
      printf "###\n###  Example: $example\n###\n"
      just {{ FLAVOUR }} $example
    done

# Build/test selected example with Docker flavour
docker-tests +DOCKER_EXAMPLES=DEFAULT_DOCKER_EXAMPLES:
    just _examples-test docker {{ DOCKER_EXAMPLES }}

vm-tests +VM_EXAMPLES=DEFAULT_VM_EXAMPLES:
    just _examples-test vm {{ VM_EXAMPLES }}

# build test examples w/ docker (TODO add filter examples or use docker_tests)
docker-examples:
    #!/usr/bin/env bash
    cd $JUST_DIR/examples
    for example in `ls -I "*.*"`; do
      echo "$example"
      just docker $example
    done

clean-nxc-test:
    @echo clean
    rm -f $TEST_TMP_DIR

# Rsynch current worktree to G5K
rsync-g5k SITE=DEFAULT_G5K_SITE:
    #!/usr/bin/env bash
    set -euxo pipefail
    rsync -avz $JUST_DIR/.. --delete --exclude '\#*' {{ SITE }}.g5k:nxc-test-src
    # change gitdir ref from absolute to relative path
    ssh grenoble.g5k "find nxc-test-src -name .git -exec sed -i 's/ .*bare/ \.\.\/\.bare/' {} \;"

oarsub-g5k-script NBNODES=DEFAULT_NBNODES WALLTIME=DEFAULT_WALLTIME:
    #!/usr/bin/env bash
    # TODO test if there is already active job
    set -euxo pipefail
    cd $JUST_DIR
    shopt -s expand_aliases && alias nxc_local="{{ nxc_local }}"
    g5k_script=$(nxc helper g5k_script)
    export $(oarsub -l nodes={{ NBNODES }},walltime={{ WALLTIME }}:0:0 \
    -O $TEST_TMP_DIR/OAR.%jobid%.stdout -E $TEST_TMP_DIR/OAR.%jobid%.stderr \
    "$g5k_script {{ WALLTIME }}h" | grep OAR_JOB_ID)
    echo $OAR_JOB_ID > $TEST_TMP_DIR/OAR_JOB_ID

start-test-g5k-nfs-store EXAMPLE:
    #!/usr/bin/env bash
    # take the repo of the last built composition
    set -euxo pipefail
     if [[ $(hostname -d) == *"grid5000"* ]] ; then
      shopt -s expand_aliases && alias nxc_local="nxc"
    else
      shopt -s expand_aliases && alias nxc_local="{{ nxc_local }}"
    fi
    compo_dir=$(ls -rtd $TEST_TMP_DIR/g5k-nfs-store/{{ EXAMPLE }}* | tail -n 1)
    OAR_JOB_ID=$(cat $TEST_TMP_DIR/OAR_JOB_ID)
    if [ -z $OAR_JOB_ID ]; then
      echo "no OAR_JOB_ID, need to submit OAR job before (oarsub_g5k_script)"
    fi
    # test if job exist ant it's in approtiate state
    oarjob_status=$(oarstat -j $OAR_JOB_ID -s)
      if [[ ! "${oarjob_status##* }" =~ ^(Waiting|Launching|Running|toLaunch|Hold|toAckReservation)$ ]]; then
         echo "Job's status issue: $oarjob_status"
        exit 1
      fi

    cd $compo_dir
    machine_file=$TEST_TMP_DIR/OAR.$OAR_JOB_ID.stdout
    nxc start -m $machine_file -W
    nxc driver -t

# build and test g5k-nfs-store flavoured test (launchable remotly or on site)
g5k-nfs-store-test SITE=DEFAULT_G5K_SITE EXAMPLE=DEFAULT_EXAMPLE NBNODES=DEFAULT_NBNODES:
    #!/usr/bin/env bash
    set -euxo pipefail
    hostname_fqdn=$(hostname --fqdn)
    if [[ $hostname_fqdn =~ "grid5000.fr" ]]; then
       if [[ $hostname_fqdn =~ "{{ SITE }}.grid5000.fr" ]]; then
         just build g5k-nfs-store {{ EXAMPLE }}
         just start_test_g5k_nfs_store {{ EXAMPLE }}
         exit
       else
         remote={{ SITE }}
       fi
    else
       remote={{ SITE }}.g5k
    fi
    echo $hostname_fqdn $remote {{ SITE }}
    ssh $remote "cd nxc-test-src/$NXC_BRANCH && just g5k_nfs_store_test"

print-examples-nixpkgs-version:
    git --no-pager grep NixOS/nixpkgs examples

# Set flakes nixpkgs (arg example: 23.11)
set-flake-nixpkgs-version version: && print-examples-nixpkgs-version
    @find . -type f -name 'flake.nix' -exec sed -i 's/github:NixOS\/nixpkgs\/.*/github:NixOS\/nixpkgs\/{{ version }}";/g' {} +

# Prune containers
docker-container-prune:
    docker container prune

develop-venv:
    # TODO: test if .venv exist it not create w/ : uv pip install -e .
    source .venv/bin/activate

develop-with-poetry:
    #!/usr/bin/env bash
    echo "execute: poetry env activate"
    nix run nixpkgs#poetry

# Launch poetry shell (from nixpkgs)
develop-with-poetry-1_8-shell:
    echo "Warning old poetry is deprecated to remove when poetru"
    nix develop .\#poetry-python311 --command $SHELL -c "poetry shell"

# Launch poetry (from nixpkgs)
poetry +commands:
    nix run nixpkgs#poetry {{ commands }}

# Create new worktree
wkt-create DIR:
    git worktree add ../{{ DIR }}

# Create new worktree to prepare the next xx.xx-dev
wkt-create-nixos-unstable DIR:
    cd ../nixos-unstable && git worktree add ../{{ DIR }}

g5k-install-nxc-nix:
    #!/usr/bin/env bash
    pip install nixos-compose
    nxc helper install-nix

g5k-uninstall-nxc-nix:
    #!/usr/bin/env bash
    pip uninstall nixos-compose
    chmod 777 -R ~/.local/share/nix
    rm -rf ~/.local/share/nix

g5k-install-just SITE:
    ssh {{ SITE }}.g5k "mkdir -p ~/.local/bin  &&curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin"

build-and-test-from-installed FLAVOUR EXAMPLE="basic":
    #!/usr/bin/env bash
    set -euxo pipefail
    mkdir -p $TEST_TMP_DIR/{{ FLAVOUR }}
    tmpdir=$(mktemp -d $TEST_TMP_DIR/{{ FLAVOUR }}/{{ EXAMPLE }}.XXXXXX)
    #prepare directory
    echo $tmpdir
    cd $tmpdir
    nxc init -f {{ FLAVOUR }} -t {{ EXAMPLE }}
    nxc build -f {{ FLAVOUR }}
    if [[ {{ FLAVOUR }} == "vm" ]]; then
      # nxc_local start -t # TOFIX
      nxc start &
      sleep 20
      nxc driver -t
      pkill qemu-system
    else
      nxc start
      nxc driver -t
      nxc stop
    fi

publish-on-pypi:
    #!/usr/bin/env bash
    if [[ {{ NXC_BRANCH }} == "master" ]]; then
       echo "Publish must be done from an XX.XX branch" && exit 1
    else
       just poetry "-- publish --build -u __token__ -p $(cat ~/tokens/nxc)"
    fi

build-tgz:
    just poetry build

g5k-install-tgz SITE="grenoble":
    #!/usr/bin/env bash
    rsync -avz dist/ --delete --exclude '*.whl' {{ SITE }}.g5k:nxc-dist
    lastest_tgz=$(ls -t dist -I '*.whl'| head -n 1)
    echo "Install $lastest_tgz on {{ SITE }} site"
    ssh {{ SITE }}.g5k "pip uninstall -y nixos-compose ; pip install nxc-dist/$lastest_tgz ; nxc --version"
