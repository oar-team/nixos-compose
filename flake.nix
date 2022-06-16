{
  description = "nixos-compose";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        #customOverrides = self: super: {
        # Overrides go here
        #};

        app = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          #overrides =
          #  [ pkgs.poetry2nix.defaultPoetryOverrides customOverrides ];
          propagatedBuildInputs = [ pkgs.openssh ];
          dontPatchShebangs = 1;
        };

        packageName = "nixos-compose";
      in rec {
        packages = {
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
        };

        defaultPackage = self.packages.${system}.${packageName};

        devShells = {
          nxcShell = pkgs.mkShell {
            buildInputs = [ self.defaultPackage.${system} ];
          };
          nxcShellFull = pkgs.mkShell {
            buildInputs = [
              self.packages.${system}.${packageName}
              pkgs.docker-compose
              pkgs.qemu_kvm
              pkgs.vde2
              pkgs.tmux
            ];
          };
        };

        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [ poetry ];
          inputsFrom = builtins.attrValues self.packages.${system};
        };

    }) //
  {lib = import ./nix/lib.nix; templates = import ./examples/nix_flake_templates.nix; overlay = import ./overlay.nix { inherit self; };};
}
