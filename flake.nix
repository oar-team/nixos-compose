{
  description = "nixos-compose";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        app = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          propagatedBuildInputs = [ pkgs.openssh ];
          dontPatchShebangs = 1;
        };

        packageName = "nixos-compose";
      in rec {
        packages = {
          default = self.packages.${system}.${packageName};
          ${packageName} = app;
          "${packageName}-full" = app.overrideAttrs (attr: rec {
            propagatedBuildInputs = attr.propagatedBuildInputs
              ++ [ pkgs.docker-compose_2 pkgs.qemu_kvm pkgs.vde2 ];
          });
          showTemplates = pkgs.writeText "templates.json" (builtins.toJSON
            (builtins.mapAttrs (name: value: value.description)
              self.templates));
        };

        devShells = {
          default = pkgs.mkShell {
            buildInputs = with pkgs; [ poetry ];
            inputsFrom = builtins.attrValues self.packages.${system};
          };
          nxcShell = pkgs.mkShell {
            buildInputs = [ self.packages.${system} ]; };
          nxcShellFull = pkgs.mkShell {
            buildInputs = [ self.packages.${system}."${packageName}-full" ];
          };
        };
      }) // {
        lib = import ./nix/lib.nix;
        templates = import ./examples/nix_flake_templates.nix;
        overlays.default = import ./overlay.nix { inherit self; };
      };
}
