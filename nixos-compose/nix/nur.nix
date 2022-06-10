# NUR helper
#
# Usage:
#  # with Flake:
#  inputs.NUR.url = "github:nix-community/NUR";
#  inputs.kapack.url = "path:/home/auguste/dev/nur-kapack";
#
#  outputs = { self, nixpkgs, NUR, kapack }: {
#  ...
#  nur = import ./nix/nur.nix {
#    inherit nixpkgs system NUR;
#    repoOverrides = { inherit kapack; };
#  };
#  extraConfigurations = [
#    # add nur attribute to pkgs
#    { nixpkgs.overlays = [ nur.overlay ]; }
#    # add wanted NUR's modules
#    nur.repos.kapack.modules.oar
#  ];
#
{ nixpkgs, system, NUR, repoOverrides ? { } }:
let nurpkgs = import nixpkgs { inherit system; };
in {
  overlay = (final: prev: {
    nur = import NUR {
      nurpkgs = prev;
      pkgs = prev;
      repoOverrides =
        builtins.mapAttrs (name: value: import value { pkgs = prev; })
        repoOverrides;
    };
  });
  repos = (import NUR {
    inherit nurpkgs;
    repoOverrides =
      builtins.mapAttrs (name: value: import value { }) repoOverrides;
  }).repos;

}
