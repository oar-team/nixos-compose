{
  description = "nixos-compose - basic setup";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-21.05";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
  };

  outputs = { self, nixpkgs, nxc }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      nixos-compose = nxc.defaultPackage.${system};
      nxcEnv = nixos-compose.dependencyEnv;

      execo_expe = pkgs.writeShellScript "execo_expe" ''
        ${nxcEnv}/bin/python3 ${./execo_script.py} $@
      '';
    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;
        composition = ./composition.nix;
      };

      apps.${system} = {
        expe = {
          type = "app";
          program = "${execo_expe}";
        };
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::nixos-test";

      devShell.${system} =
        pkgs.mkShell { buildInputs = [ nixos-compose ]; };
    };
}
