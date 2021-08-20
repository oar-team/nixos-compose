{
  description = "nixos-compose - composition to infrastructure";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs?rev=7e9b0dff974c89e070da1ad85713ff3c20b0ca97";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";

      composition = import ./composition.nix;

      nixos_test = import ./nix/nixos-test.nix;
      generate = import ./nix/generate.nix;
      compose = import ./nix/compose.nix;
      flavours = import ./nix/flavours.nix;

    in {
      packages.x86_64-linux = nixpkgs.lib.mapAttrs (name: flavour:
        compose { inherit nixpkgs system flavour composition; }) flavours // {
          nixos-test = nixos_test { inherit nixpkgs system; } composition;
          nixos-test-driver =
            (nixos_test { inherit nixpkgs system; } composition).driver;
        };
      defaultPackage.x86_64-linux = self.packages.x86_64-linux.nixos-test;
    };
}
