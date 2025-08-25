{
  description = "nixos-compose - simple mutiple compositions";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
  };

  outputs = { self, nixpkgs, nxc }:
    let
      system = "x86_64-linux";
    in {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;
        compositions = ./compositions.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."linux_5_4::vm";

      devShell.${system} = nxc.devShells.${system}.nxcShell;
    };
}
