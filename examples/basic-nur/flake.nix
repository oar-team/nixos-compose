{
  description = "nixos-compose - composition to infrastructure";

  inputs.NUR.url = "github:nix-community/NUR";
  #inputs.alice.url = "path:/home/some_path/nur-alice";

  outputs = { self, nixpkgs, NUR }:
    let
      system = "x86_64-linux";

      flavours = import ./nix/flavours.nix;

      nur = import ./nix/nur.nix {
        inherit nixpkgs system NUR;
        # for repo override if needed
        #repoOverrides = { inherit alice; };
      };

      extraConfigurations = [
        # add nur attribute to pkgs
        {
          nixpkgs.overlays = [ nur.overlay ];
        }
        #nur.repos.alice.modules.foo
      ];

    in {
      packages.${system} =
        (import ./nix/compose.nix) { inherit nixpkgs system flavours; };

      defaultPackage.${system} =
        self.packages.${system}."composition::nixos-test";
    };
}
