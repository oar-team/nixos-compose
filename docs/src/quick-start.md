The intent of this guide is to go through the different commands made available by `nxc`. We will depict the workflow while you are setting up your environments or running an experiment. We are not yet going in detail into the content of a composition neither how to write it.

<!-- The following guide goes through a basic example with a complete focus on the commands, it does not go in detail in the content of a composition. It's a reminder of the commands to use when interacting with a project. It depicts the workflow intended by _NixOSCompose_. -->

<!-- TODO écrire que ce sera docker puis g(kramdisk) -->

<!--  est ce que je simplifie le tout :/ dans le sens ou je donne moins d'alternative et je vais droit au but ? ... -->

```admonish todo
meant to be iteractive, multiple run done locally
```

# Local usage

It is convenient to work locally during the development phase or during the configuration of the software environment, as it allows for fast development cycles. _NixOSCompose_ allows to quickly iterate with docker containers or VMs, and it avoids using testbed platforms during early testing phases.

Later, when our composition is ready, we will deploy it to Grid5000.

## Initialization of a project

There are some templates (using the template mechanism of _Nix_ flakes) that provide the boilerplate to start a project. You can do this either with a locally available _NixOSCompose_ or with the `nix flake` command. It will copy all necessary files. You can use these commands on a new folder or for your existing project folder.

For the following, we are using the `basic` template. It is a composition that describes an evironment composed of one node called `foo` that contains nothing.

- _Nix_ flake's template

    To avoid writting the full path to the _NixOSCompose_ flake we are using the _Nix_ registries.
    ```shell
    nix registry add nxc git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git
    ```
    So now in any _Nix_ flake related command writting `nxc#` will be equivalent to `git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git#`.
    ```shell
    # initialize current folder
    nix flake init -t nxc#basic
    # or initialize projectFolder
    nix flake new projectFolder -t nxc#basic
    ```
- local _NixOSCompose_

    Using your locally installed _NixOSCompose_ the commands are the following.
    ```shell
    cd nixos-compose
    nix develop .#nxcShellLite
    cd path/to/projectFolder
    nxc init -t basic
    ```
    You can then quit the `nix-shell` provided by the command `nix develop` with `Ctrl-d`.


At the end you end up with this:
```shell
$ tree projectFolder
projectFolder
├── composition.nix
├── flake.nix
└── nxc.json

0 directories, 3 files
```

These 3 files are the minimum requiered by _NixOSCompose_.

- `flake.nix` is the entry point for a _Nix_ project, it defines all the dependencies and exposes differents outputs, like `devShells` or `packages`.
- `composition.nix` where the configuration of the roles needed by your experiment is described. 
- `nxc.json` defines a few default variables for _NixOSCompose_.

All those files need to be tracked by Git. _Nix_ flakes even require it to work properly.

```shell
git init && git add *
```

If your project is already using git you just need to add those files.

```
git add flake.nix composition.nix nxc.json
```

## Overview of `composition.nix`

Nodes are listed under the field `nodes` and we can see that we have one node called `foo`.

```nix
{ pkgs, ... }: {
nodes = {
    foo = { pkgs, ... }:
    {
        # add needed package
        # environment.systemPackages = with pkgs; [ socat ];
    };
};
testScript = ''
    foo.succeed("true")
'';
}
```

## Local development and usage

First enter the `nxc` shell. Here we choose `nxcShell` because it provides all necessary dependencies to run the composition locally (e.g. docker-compose).

```shell
cd path/to/projectFolder
nix develop .#nxcShell
```

```admonest info
The first call to `nix develop` can take quite some time because it will fetch and/or build all depedencies for the `nxc` shell. Later calls to this command would be faster because everything will already be present in the _Nix_ store (on condition that the flake's inputs did not change).
```

### Building 

The composition can then be built. The command below will evaluate the composition file then build the necessary artifacts for a local deployment using docker containers. The files generated at build time for the different flavours are put in a new `build` folder. As we are building the `docker` flavour, it hosts the docker-compose file for our composition.

```shell
nxc build -f docker
```

```admonest info
If there is an error in the nix code this is when it would show up.
```

### Local deployment

#### 1. Start

The local deployment is done thanks to the command below. The option `-f docker` says that we explicitly want to deploy the composition with the docker flavour. This option is optional. If called without it, the command would choose the most recently built flavour.

```shell
nxc start -f docker
```

You can check that the corresponding container has been launched.

```shell
$ docker ps --format '{{.Names}}'
docker_compose_foo_1
```

```admonest info
The `build` folder does not need to be tracked by git.
```

#### 2. Interact

You can connect to the node with
```shell
nxc connect foo
```
which will open a shell in the container `foo`.

<!-- An other mean to interact with the deployed environment is through the driver. It is python repl in wich you wan interecat with all nodes with some advanced features. See [Driver](driver.md)
```
nxc driver
``` -->

#### 3. Stop

Lastly the virtualized environment can be stopped with the following command. It stops the container previously launched. 

```shell
nxc stop
```

### Edition and test loop

The three steps above plus the editing of the composition create a convenient "Edit - Test" loop. It allows to quickly iterate on the set up of the environments. At some point the configurations converge to something satisfactory and physicial deployment is the next step.

# Physical deployment on Grid5000

At first you need to import your project to your home folder on Grid5000 with your prefered method (rsync, git, ...).

## Building on Grid5000

This phase requires the reservation of a node in interactive mode with `oarsub -I`. Once you have access to the node you need to activate _Nix_ with the script `nix-user-chroot.sh` (see [grid5000 install](install/grid5000.md#nix-chroot-sur-frontale--nix-develop))
```shell
./nix-user-chroot.sh
```

Enter the `nix-shell` that provides the `nxc` command.
```shell
cd path/to/project
nix develop .#nxcShellLite
```

You can now to build the `g5k-ramdisk` flavour.

```shell
nxc build -f g5k-ramdisk
```

Since the _Nix_ store is shared between the frontend and the build node, all created artifacts will then be available from the frontend for the deployment. Everything will stay accessible from the `build` folder.

Once the building is done you can release the Grid5000 ressource.

## Deployment

The first step is to claim the ressources needed by the project, here only 1 node.

enter virtual env that contains nxc

```admonest todo
TODO: add the virtualenv version
```

```shell
cd path/to/nixos-compose
poetry shell
```
### Ressource reservation

The reservation through the command line needs the command below, it requests one node for 30 minutes. At the same time it lists the machines in the `stdout` file associated to the reservation ( `OAR.<oar_job_id>.sdtout` ) and defines the `$OAR_JOB_ID` environment variable. This information are needed for the next step.

```shell
cd path/to/project
export $(oarsub -l nodes=1,walltime=0:30 "$(nxc helper g5k_script) 30m" | grep OAR_JOB_ID)
```

```admonish warning tip abstract 
The command above asks OAR for some ressources, then execute a script that sends the user public key to the nodes.
~~~console
export $(oarsub -l nodes=<NODES>,walltime=<TIME1> "$(nxc helper g5k_script) <TIME2>" | grep OAR_JOB_ID)
~~~
- NODES : number of nodes needed for the experiment.
- TIME1 : duration of the reservation with `h:minute:second` syntax (see [Grid5000 wiki]())
- TIME2 : duration of the `sleep` command sended to the nodes, usualy same lenght as the reservation duration. Syntax available in [coreutils documentation](https://www.gnu.org/software/coreutils/manual/html_node/sleep-invocation.html#sleep-invocation)
```

Once the ressoruces are available the `OAR.$OAR_JOB_ID.stdout` file is created.

```shell
$ cat OAR.$OAR_JOB_ID.stdout
dahu-7.grenoble.grid5000.fr
```

### Actual deployment

At this step we have ressources available and the composition has been built in the desired flavour, `g5k-ramdisk`. We can now launch the deployment. The command is similar to a local virtualized deployment exept for the option `-m` that requiered a file that list all remote machines covered by our deployment. If you used the command seen at the previous step the list of machine is in the `OAR.$OAR_JOB_ID.stdout` file.

```shell
nxc start -f g5k-ramdisk -m OAR.$OAR_JOB_ID.stdout
```
### Interact

Similarly than with docker run locally, the command below will open a shell in the `foo` node.

```shell
nxc connect foo
```

### Release of ressources

Once you finished with the node you can release the ressources.

```shell
oardel $OAR_JOB_ID
```
