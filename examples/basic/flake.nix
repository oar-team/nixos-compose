{
  description = "nixos-compose - basic setup";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/23.05";
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

      devShell.${system} = nxc.devShells.${system}.nxcShell;
    };
}
