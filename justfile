export JUST_DIR := justfile_directory()
export NXC_BRANCH := `basename $PWD`

# nxc command from local source version

nxc_local := "nix develop --override-input nxc path:" + justfile_directory() + " -c nxc"

#examples:= `cd examples && ls -I "*.*"`

DEFAULT_COMMON_EXAMPLES := "basic basic-nur execo multi-compositions nbp-mpi nixos-cluster scripts setup shared-directories-users webserver"
DEFAULT_DOCKER_EXAMPLES := DEFAULT_COMMON_EXAMPLES
DEFAULT_VM_EXAMPLES := DEFAULT_COMMON_EXAMPLES + " kernel"
DEFAULT_G5K_EXAMPLES := DEFAULT_COMMON_EXAMPLES + " kernel"
DEFAULT_G5K_SITE := "grenoble"
export TEST_TMP_DIR := `echo $HOME` + "/nxc-test-tmp"
DEFAULT_NBNODES := "1"
DEFAULT_WALLTIME := "1:0"
DEFAULT_EXAMPLE := "basic"

alias b := build
alias d := develop_with_poetry
alias p := poetry
default:
    @just --list

_copy_prepare_example TMPDIR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    cp -a examples/{{EXAMPLE}}/* {{TMPDIR}}
    cd {{TMPDIR}}
    git init && git add *

build_and_test FLAVOUR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    mkdir -p $TEST_TMP_DIR/{{FLAVOUR}}
    tmpdir=$(mktemp -d $TEST_TMP_DIR/{{FLAVOUR}}/{{EXAMPLE}}.XXXXXX)
    #prepare directory
    just _copy_prepare_example $tmpdir {{EXAMPLE}}
    cd $tmpdir
    shopt -s expand_aliases && alias nxc_local="{{nxc_local}}"
    nxc_local build -f {{FLAVOUR}}
    if [[ {{FLAVOUR}} == "vm" ]]; then
      nxc_local start -t
    else
      nxc_local start
      nxc_local driver -t
      nxc_local stop
    fi

build FLAVOUR EXAMPLE:
    #!/usr/bin/env bash
    set -euxo pipefail
    mkdir -p $HOME/nxc-test-tmp/{{FLAVOUR}}
    tmpdir=$(mktemp -d $TEST_TMP_DIR/{{FLAVOUR}}/{{EXAMPLE}}.XXXXXX)
    #prepare directory
    just _copy_prepare_example $tmpdir {{EXAMPLE}}
    cd $tmpdir
    shopt -s expand_aliases && alias nxc_local="{{nxc_local}}"
    nxc_local build -f {{FLAVOUR}}

docker EXAMPLE:
    just build_and_test docker {{EXAMPLE}}

vm EXAMPLE:
    just build_and_test vm {{EXAMPLE}}

list_examples:
    #!/usr/bin/env bash
    cd $JUST_DIR/examples
    for example in `ls -I "*.*"`; do echo "$example"; echo poy; done

_examples_test FLAVOUR +EXAMPLES:
    #!/usr/bin/env bash
    for example in {{EXAMPLES}} ; do
      printf "###\n###  Example: $example\n###\n"
      just {{FLAVOUR}} $example
    done

# Build/test selected example with Docker flavour
docker_tests +DOCKER_EXAMPLES=DEFAULT_DOCKER_EXAMPLES:
    just _examples_test docker {{DOCKER_EXAMPLES}}

vm_test +VM_EXAMPLES=DEFAULT_VM_EXAMPLES:
    just _examples_test vm {{VM_EXAMPLES}}

# build test examples w/ docker (TODO add filter examples or use docker_tests)
docker_examples:
    #!/usr/bin/env bash
    cd $JUST_DIR/examples
    for example in `ls -I "*.*"`; do
      echo "$example"
      just docker $example
    done

clean_nxc_test:
    @echo clean
    rm -f $TEST_TMP_DIR

# Rsynch current worktree to G5K (remove reference to .bare in . git)
rsync_g5k SITE=DEFAULT_G5K_SITE:
    #!/usr/bin/env bash
    set -euxo pipefail
    rsync -avz $JUST_DIR/.. --exclude '\#*' {{SITE}}.g5k:nxc-test-src
    ssh grenoble.g5k "find nxc-test-src -name .git -exec sed -i 's/ .*bare/ \.\.\/\.bare/' {} \;"

oarsub_g5k_script NBNODES=DEFAULT_NBNODES WALLTIME=DEFAULT_WALLTIME:
    #!/usr/bin/env bash
    # TODO test if there is already active job
    set -euxo pipefail
    cd $JUST_DIR
    g5k_script=$HOME/.local/share/nix/root/$(nix run .#nixos-compose helper g5k_script)
    export $(oarsub -l nodes={{NBNODES}},walltime={{WALLTIME}} \
    -O $TEST_TMP_DIR/OAR.%jobid%.stdout -E $TEST_TMP_DIR/OAR.%jobid%.stderr \
    "$g5k_script 1h" | grep OAR_JOB_ID)
    echo $OAR_JOB_ID > $TEST_TMP_DIR/OAR_JOB_ID

start_test_g5k_nfs_store EXAMPLE:
    #!/usr/bin/env bash
    # take the repo of the last built composition
    set -euxo pipefail
    compo_dir=$(ls -rtd $TEST_TMP_DIR/g5k-nfs-store/{{EXAMPLE}}* | tail -n 1)
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
g5k_nfs_store_test SITE=DEFAULT_G5K_SITE EXAMPLE=DEFAULT_EXAMPLE NBNODES=DEFAULT_NBNODES:
    #!/usr/bin/env bash
    set -euxo pipefail
    hostname_fqdn=$(hostname --fqdn)
    if [[ $hostname_fqdn =~ "grid5000.fr" ]]; then
       if [[ $hostname_fqdn =~ "{{SITE}}.grid5000.fr" ]]; then
         just build g5k-nfs-store {{EXAMPLE}}
         just start_test_g5k_nfs_store {{EXAMPLE}}
         exit
       else
         remote={{SITE}}
       fi
    else
       remote={{SITE}}.g5k
    fi
    echo $hostname_fqdn $remote {{SITE}}
    ssh $remote "cd nxc-test-src/$NXC_BRANCH && just g5k_nfs_store_test"

print_examples_nixpkgs_version:
    git --no-pager grep NixOS/nixpkgs examples

# Set flakes nixpkgs (arg example: 23.11)
set_flake_nixpkgs_version version: && print_examples_nixpkgs_version
    @find . -type f -name 'flake.nix' -exec sed -i 's/github:NixOS\/nixpkgs\/.*/github:NixOS\/nixpkgs\/{{version}}";/g' {} +

# Prune containers
docker_container_prune:
    docker container prune

# Launch poetry shell (from nixpkgs)
develop_with_poetry:
    nix run nixpkgs#poetry shell

# Launch poetry (from nixpkgs)
poetry +commands:
    nix run nixpkgs#poetry {{commands}}

# Create new worktree
wkt-create DIR:
    git worktree add {{DIR}}
