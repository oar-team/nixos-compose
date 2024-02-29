The installation and usage of _NixOSCompose_ differs in function of the state at which the project you are working on is. In the case of a new project you will want to install the `nxc` command line tool as it is described in [Local Installation](local.md#local-installation). If the project you are working on is already using _NixOSCompose_ because you are developing it or in the case of the re-run of an experiment conducted in the past, you will prefer to use the version of `nxc` link to the project. Invoking `nxc` in an embedded way is described in [Linked/project embedded `nxc`](local.md#project-embedded-nxc)

# Requirements

- Nix package manager with flake feature activated (see [NixOS website](https://nixos.org/download.html) and [NixOS wiki](https://nixos.wiki/wiki/Flakes#Installing_flakes))

```admonish note title="Quick note from NixOS wiki to activate flake feature"
- Non-NixOS

    Edit `~/.config/nix/nix.conf` to add this line :
    ```
    experimental-features = nix-command flakes
    ```
- NixOS

    Edit your configuration by adding the following options
    ```nix
    { pkgs, ... }: {
        nix = {
            package = pkgs.nixFlakes; # or versioned attributes like nixVersions.nix_2_8
            extraOptions = ''
                experimental-features = nix-command flakes
            '';
        };
    }
    ```
```

## Configuration requirements

On NixOS you need to enable the dockers functionnality, in our case there is a compatibility issue with cgroupv2 so it is needed to force cgroupv1 with the option `systemd.enableUnifiedCgroupHierarchy`.

```nix
# Docker enabled + cgroup v1
virtualisation.docker.enable = true;
systemd.enableUnifiedCgroupHierarchy = false;
```


# Local installation

The following commands will drop you in a shell where the `nxc` command is available and all required runtime dependencies (docker-compose, vde2, tmux, qemu_kvm).

```shell
git clone https://gitlab.inria.fr/nixos-compose/nixos-compose.git
cd nixos-compose
nix develop .#nxcShellFull
```
## Alternative

You can take advantage of the full potential of Nix's flakes. The following command will drop you in the same shell without having to clone the repository.
```shell
nix develop https://gitlab.inria.fr/nixos-compose/nixos-compose.git#nxcShellFull
```

~~~admonish tip
Writting the full url is not really practical, an "alias" can be used.
```shell
nix registry add nxc git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git
```
The command becomes :
```shell
nix develop nxc#nxcShellFull
```
~~~

# Project embedded `nxc`

A project that is already using _NixOSCompose_ in its experiments process provides an easy access to a shell that gives access to the `nxc` tool and its runtime dependencies if needed. This is achieved thanks to Nix and its flakes feature. By default, a project has a line in its `flake.nix` similar to this :

```nix
devShell.${system} = nxc.devShells.${system}.nxcShellFull;
```

It exposes the shell of _NixOSCompose_ as in the previous section but with the specific revision thanks to the `flake.lock` file. The shell is accessible with the command `nix develop`. It is useful to explore what shells are available in the project, to list them you use `nix flake show`. Then to access the devShell of your choice use this command :

```shell
nix develop .#nxcShellFull
```

```admonish info
Two shells availables :
- `nxcShell`
    - python app `nxc`

- `nxcShellFull`
    - python app `nxc`
    - docker-compose
    - vde2
    - tmux
    - qemu_kvm
```
