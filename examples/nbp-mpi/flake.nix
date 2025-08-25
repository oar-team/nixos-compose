{
  description = "nixos-compose - ";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
    nxc.inputs.nixpkgs.follows = "nixpkgs";
    NUR.url = "github:nix-community/NUR";
    kapack.url = "github:oar-team/nur-kapack?ref=regale";
    kapack.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, nxc, NUR, kapack }:
    let
      system = "x86_64-linux";
    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system NUR;
        repoOverrides = { inherit kapack; };
        composition = ./composition.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::docker";

      devShell.${system} = nxc.devShells.${system}.nxcShell;
    };
}
