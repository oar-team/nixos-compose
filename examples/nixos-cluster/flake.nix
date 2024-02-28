{
  description = "nixos-compose - basic setup";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/23.05";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
  };

  outputs = { self, nixpkgs, nxc }:
    let
      system = "x86_64-linux";
      myOverlay = final: prev: {
        nixos-compose = nxc.packages.${system}.nixos-compose;
      };
    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;
        overlays = [ myOverlay ];
        composition = ./composition.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::vm";

      devShell.${system} = nxc.devShells.${system}.nxcShellFull;
    };
}
