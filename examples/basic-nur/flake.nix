{
  description = "nixos-compose - basic setup with external NUR repo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/22.05";
    NUR.url = "github:nix-community/NUR";
    nxc.url = "git+https://gitlab.inria.fr/nixos-compose/nixos-compose.git";
    #inputs.alice.url = "path:/home/some_path/nur-alice";
  };

  outputs = { self, nixpkgs, NUR, nxc }:
    let
      system = "x86_64-linux";

      nur = nxc.lib.nur {
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
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system extraConfigurations;
        composition = ./composition.nix;
      };

      defaultPackage.${system} =
        self.packages.${system}."composition::nixos-test";

      devShell.${system} = nxc.devShells.${system}.nxcShell;
    };
}
