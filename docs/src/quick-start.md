The intent of this guide is to go through the different commands made available by `nxc`, the goal is to depict the workflow while you are setting up your environments or running an experiments. We are not going in detail into the content of a composition neither how to write it.


<!-- The following guide goes through a basic example with a complete focus on the commands, it does not go in detail in the content of a composition. It's a reminder of the commands to use when interacting with a project. It depicts the workflow intended by _NixOSCompose_. -->

<!-- TODO écrire que ce sera docker puis g(kramdisk) -->

<!--  est ce que je simplifie le tout :/ dans le sens ou je donne moins d'alternative et je vais droit au but ? ... -->



meant to be iteractive, multiple run done locally
# Local usage

## Initialization of a project

The initialization step uses the template mechanism of _Nix_ flakes. This step can be completed with a locally available _NixOSCompose_ or with the `nix flake` command. It will copy all necessary files. You can decide to either initialize a new folder or initialize your current project folder. For the following steps we are using the `basic` template. It is a composition that describes an evironment composed of one node called `foo` that contains nothing.

- _Nix_ flake template feature

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
    nix develop .#nxcShell
    cd path/to/projectFolder
    nxc init -t basic
    ```
    You can then quit the `nix-shell` provided by the command `nix develop` with `Ctrl-d`.


At the end you end up with this :
```shell
$ tree projectFolder
projectFolder
├── composition.nix
├── flake.nix
└── nxc.json

0 directories, 3 files
```
These 3 files are the minimum requiered by _NixOSCompose_.

- `flake.nix` is the entry point for a _Nix_ project, it defines all the dependencies and exposes differents outputs, like `devShells` or `packages`
- `composition.nix` where is described the configuration of the roles needed by your experiment. 
- `nxc.json` a config file that defines a few default variables for _NixOSCompose_.

All those files need to be track by Git, _Nix_ flakes requieres it to works properly.

```
git init && git add *
```

If your project is already using git subversionning tracking you just need to add those files.
```
git add flake.nix composition.nix nxc.json
```

~~~admonish example title="Overview of `composition.nix`"
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
~~~

## Local development and usage

Working locally during the development phase or during environment configuration of a distributed system is convenient, _NixOSCompose_ allows to quickly iterate with docker containers or VMs, and it avoids using testbed platforms during early testing phases. 

First enter the `nxc` shell. Here we choose `nxcShellFull` because it provides al necessary dependencies to run the composition locally (e.g. docker-compose).
```console
cd path/to/projectFolder
nix develop .#nxcShellFull
```
>**Note**
>
>The first call to `nix develop` can take quiet some time because it will fetch and/or build all depedencies for `nxc` shell. Further call to this command (on condition that flake's inputs didn't change) would be faster because everything will already be present in the _Nix_ store.

### Building 

The composition can then be built, the command below will evaluate the composition file then build the necessary artifacts for a local deployment using docker containers. The folder `build` is created, it receives the files generated at build time for the different flavours, in `docker` flavour case it hosts the docker-compose file.

```
nxc build -f docker
```

> Note
>
> If there is an error in the nix code this is when it would show up.

### Local deployment

#### 1 - Start
The local deployment is done thanks to the command below. The option `-f docker` says that we explicitly want to deploy the composition with the docker flavour. This option is optional, if called without it the command will choose the most recently built flavour.
```
nxc start -f docker
```

You can check that the corresponding container has been launched.
```console
$ docker ps --format '{{.Names}}'
docker_compose_foo_1
```

> Note
>
> The `build` folder does not need to be tracked by git.

#### 2. Interact

You can connect to the node, `nxc connect foo` will open a shell in the container `foo`.
```
nxc connect foo
```

<!-- An other mean to interact with the deployed environment is through the driver. It is python repl in wich you wan interecat with all nodes with some advanced features. See [Driver](driver.md)
```
nxc driver
``` -->

#### 3. Stop

Lastly the virtualized environment can be stopped with the following command. It stops the container previously launched. 
```
nxc stop
```
### "Edit - Test" loop

The three steps above plus the editing of the composition create a convenient "Edit - Test" loop. It allows to quickly iterate on the set up of the environments. At some point the configurations converge to something satisfactory and physicial deployment is the next step.

# Physical deployment on Grid5000

At first you need your project in your home folder on Grid5000  with your prefered method (rsync, git, ...).

## Building on Grid5000

This phase requires the reservation of a node in interactive mode with `oarsub -I`. Once you have access to the node you need to activate _Nix_ with the script `nix-user-chroot.sh` (see [grid5000 install](install/grid5000.md#nix-chroot-sur-frontale--nix-develop))
```console
./nix-user-chroot.sh
```

Enter the `nix-shell` that provides the `nxc` app.
```
cd path/to/project
nix develop .#nxcShell
```

You are now able to build using the `g5k-ramdisk` flavour. Since the _Nix_ store is shared between the frontend and the build node, all created artifacts will then be available from the frontend for the deployment. Everything will stay accessible from the `build` folder.
```
nxc build -f g5k-ramdisk
```

Once the building is done you can release the ressource.

## Deployment

The first step is to claim the ressources needed by the project, here only 1 node.
enter virtual env that contains nxc
```console
. path/to/virtual/env

# or with local poetry
cd path/to/nixos-compose
poetry shell
```

Reservation
```
cd path/to/project
export $(oarsub -l nodes=4,walltime=1:00 "$(nxc helper g5k_script) 1h" | grep OAR_JOB_ID)
```
nxc start -f g5k-ramdisk -m OAR.$OAR_JOB_ID.stdout
```


nxc connect foo
interact
then release





so so so il faut etre en python virtual env sinon pas de déploiement.... en théorie si mais bon
