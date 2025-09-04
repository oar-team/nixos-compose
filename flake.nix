{
  description = "nixos-compose";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";
    kapack.url = "github:oar-team/nur-kapack/25.05";
    kapack.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, kapack }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          mdbook-admonish =
            nixpkgs.legacyPackages.${system}.callPackage ./docs/mdbook-admonish.nix { };
          pkgs = nixpkgs.legacyPackages.${system};
          python3pkgs = pkgs.python3Packages;
          kapackpkgs = kapack.packages.${system};

          #customOverrides = self: super: {
          # Overrides go here
          #};

          app = python3pkgs.buildPythonPackage rec {
            pname = "nxc";
            version = "locale";
            name = "${pname}-${version}";

            src = builtins.filterSource
              (path: type: type != "directory" || baseNameOf path != ".git" || path != "result")
              ./.;

            format = "pyproject";
            buildInputs = [ pkgs.poetry ];
            propagatedBuildInputs = with python3pkgs; [
              poetry-core
              click
              kapackpkgs.execo
              halo
              pexpect
              psutil
              ptpython
              pyinotify
              pyyaml
              requests
              tomlkit
              setuptools
            ] ++ [ pkgs.taktuk pkgs.nix-output-monitor ];
          };

          doc = import ./docs/doc.nix { inherit nixpkgs pkgs system; };

          packageName = "nixos-compose";
        in {
          packages = {
            ${packageName} = app;
            # "${packageName}-full" = app.overrideAttrs(attr: rec {
            #   propagatedBuildInputs = attr.propagatedBuildInputs ++ [
            #     pkgs.docker
            #     pkgs.qemu_kvm
            #     pkgs.vde2
            #   ];
            # });
            showTemplates = pkgs.writeText "templates.json" (
              builtins.toJSON (builtins.mapAttrs (name: value: value.description) self.templates)
            );
          } // flake-utils.lib.flattenTree doc;

          defaultPackage = self.packages.${system}.${packageName};

          devShells = {
            nxcShellLite = pkgs.mkShell {
              buildInputs = [
                self.defaultPackage.${system}
                pkgs.tmux
              ];
            };
            nxcShell = pkgs.mkShell {
              buildInputs = [
                (pkgs.python3.withPackages (ps: [
                    kapackpkgs.execo
                    self.packages.${system}.${packageName}
                ]))
                pkgs.docker
                pkgs.qemu_kvm
                pkgs.vde2
                pkgs.tmux
                pkgs.nmap
              ];
            };
            devDoc = pkgs.mkShell {
              buildInputs = with pkgs; [ mdbook mdbook-mermaid mdbook-admonish ];
            };

            default = pkgs.mkShell {
              buildInputs = with pkgs; [ poetry ];
              # inputsFrom = builtins.attrValues self.packages.${system};
              inputsFrom = [ self.packages.${system}.${packageName} ];
            };

            poetry-python311 = let
              overlays = [
                (final: prev: {
                  poetry = prev.poetry.override { python3 = prev.python311; };
                })
              ];
              pkgs_python311 = import nixpkgs {
                inherit system overlays;
              };
            in
              pkgs_python311.mkShell {
               buildInputs = with pkgs_python311; [
                 python311
                 poetry
               ];
               shellHook = ''
                echo "Python version: $(python --version)"
                echo "Python used by poetry : $(poetry run python --version)"
               '';
            };

          };

        }) //
    { lib = import ./nix/lib.nix; templates = import ./examples/nix_flake_templates.nix; overlay = import ./overlay.nix { inherit self; }; };
}
