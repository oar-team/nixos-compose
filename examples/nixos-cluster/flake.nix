{
  description = "nixos-compose - basic setup";

  inputs = {
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-21.05";
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git?rev=b9a730ada6fe6e5f31069837f68e7fc580f8633a";
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
        self.packages.${system}."composition::nixos-test";

      devShell.${system} = nxc.devShells.${system}.nxcShellFull;
    };
}
