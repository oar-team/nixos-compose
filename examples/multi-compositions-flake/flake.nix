{
  description = "nixos-compose - composition to infrastructure";

  inputs.NUR.url = "github:nix-community/NUR";
  #inputs.alice.url = "path:/home/some_path/nur-alice";

  outputs = { self, nixpkgs, NUR }:
    let
      system = "x86_64-linux";

      compositions = import ./compositions.nix;
      flavours = import ./nix/flavours.nix;

      nur = import ./nix/nur.nix {
        inherit nixpkgs system NUR;
        # for repo override if needed
        #repoOverrides = { inherit alice; };
      };

      extraConfigurations = [
        # add nur attribute to pkgs
        { nixpkgs.overlays = [ nur.overlay ]; }
        #nur.repos.alice.modules.foo
      ];

    in {
    packages.${system} = (import ./nix/multiple_compose.nix) {
      inherit nixpkgs system compositions flavours extraConfigurations;
    };

    defaultPackage.${system} = self.packages.${system}.foo_nixos-test;
  };
}
