tuto on pythoneri insert script bash ...


Here we complete the quick start guide that was focused on the CLI, we will go further in detail with how to write the composition file, how to import personal software and the different files of a _NixOSCompose_ project.

~ Here we will go through a complete workflow with the local test deployment with docker and a Grid5000 deployment of a Nginx server and a test client.

- initialization
  - review of the files
  - launch/test
- Edit the composition
  - add a benchmark tool
  - launch/test
  - add a custom script ?
  -

# Initialization

First let's create a folder for our project locally, we are creating it with the template mechanism of _Nix_ flakes. The template that we are importing is a client/server architecture, the server hosts a Nginx webserver.

```
nix flake new webserver -t nxc#webserver
```

~~~admonish info
    To avoid writing the full path to the _NixOSCompose_ flake we are using the _Nix_ registries.
    ```shell
    nix registry add nxc git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git
    ```
~~~

If we inspect the content of our new created folder we obtain this.
```
$ tree webserver
webserver/
├── composition.nix
├── flake.nix
└── nxc.json

0 directories, 3 files
```

## Description of the files

### `flake.nix`
  A file that is key in the reproducibility of project. It defines all the dependencies of a project and what it is able to provide as outputs
  You can learn a bit onto how a flake file works [here](https://nix-tutorial.gitlabpages.inria.fr/nix-tutorial/flakes.html).

  This file manages the dependencies and the outputs of a project. It has multiple fields :
   - description
   - inputs
   - outputs

  The **description** is a string that describes the flake.

  The inputs is a set defining
  ```nix
  {
    description = "nixos-compose - basic webserver setup";

    inputs = {
      nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
      nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
    };

    outputs = { self, nixpkgs, nxc }:
    let
      system = "x86_64-linux";
    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;
        composition = ./composition.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::vm";

      devShell.${system} = nxc.devShells.${system}.nxcShellLite;
    };
  }
  ```


- `composition.nix`
    ```nix
    { pkgs, ... }: {
    nodes = {
        server = { pkgs, ... }: {
        services.nginx = {
            enable = true;
            # a minimal site with one page
            virtualHosts.default = {
            root = pkgs.runCommand "testdir" { } ''
                mkdir "$out"
                echo hello world > "$out/index.html"
            '';
            };
        };
        networking.firewall.enable = false;
        };
        client = { ... }: { };
    };
    testScript = ''
        server.wait_for_unit("nginx.service")
        client.wait_for_unit("network.target")
        assert "hello world" in client.succeed("curl -sSf http://server/")
    '';
    }
    ```
- `nxc.json`
    ```json
    {"composition": "composition.nix", "default_flavour": "vm"}
    ```
<!-- # Edit of composition

# Build

# Test in docker

## Driver
## TestScript
# Import on g5k

# Build on g5k
## build reservation

# run on G5K
## reservation
## start
## connect -->
