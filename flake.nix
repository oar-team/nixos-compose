{
  description = "nixos-compose";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/22.05";
    flake-utils.url = "github:numtide/flake-utils";
    kapack.url = "github:oar-team/nur-kapack";
    kapack.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, kapack }:
    flake-utils.lib.eachDefaultSystem (system:
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
          buildInputs = [ python3pkgs.poetry ];
          propagatedBuildInputs = with python3pkgs; [
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
          ] ++ [ pkgs.taktuk ];
        };

        doc = import ./docs/doc.nix { inherit nixpkgs pkgs system; };

        packageName = "nixos-compose";
      in rec {
        packages = {
          default = self.packages.${system}.${packageName};
          ${packageName} = app;
          # "${packageName}-full" = app.overrideAttrs(attr: rec {
          #   propagatedBuildInputs = attr.propagatedBuildInputs ++ [
          #     pkgs.docker-compose
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
          default = pkgs.mkShell {
            buildInputs = with pkgs; [ poetry ];
            inputsFrom = builtins.attrValues self.packages.${system};
          };
          nxcShell = pkgs.mkShell {
            buildInputs = [ self.packages.${system}.default ]; };
          nxcShellFull = pkgs.mkShell {
            buildInputs = [
              self.packages.${system}.${packageName}
              pkgs.docker-compose
              pkgs.qemu_kvm
              pkgs.vde2
              pkgs.tmux
            ];
          };
          devDoc = pkgs.mkShell {
            buildInputs = with pkgs; [ mdbook mdbook-mermaid mdbook-admonish ];
          };
        };
      }) // {
        lib = import ./nixos-compose/nix/lib.nix;
        templates = import ./nixos-compose/examples/nix_flake_templates.nix;
        overlays.default = import ./overlay.nix { inherit self; };
      };
}
