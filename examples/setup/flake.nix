{
  description = "nixos-compose - setup feature";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-21.05";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
  };

  outputs = { self, nixpkgs, nxc }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;
        setup = ./setup.toml;
        composition = ./composition.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::nixos-test";

      devShell.${system} =
        pkgs.mkShell { buildInputs = [ nxc.defaultPackage.${system} ]; };
    };
}