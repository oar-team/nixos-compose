{
  description = "nixos-compose - basic setup";

  inputs = { nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable"; };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";

      flavours = import ./nix/flavours.nix;

    in {
      packages.${system} =
        (import ./nix/compose.nix) { inherit nixpkgs system flavours; };

      defaultPackage.${system} =
        self.packages.${system}."composition::nixos-test";
    };
}
