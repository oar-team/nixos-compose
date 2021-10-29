rec {
  # funtion to multiple node based on the same configuration
  makeManyById = base_conf_by_id: name: count:
    let
      f = n: s:
        if n == 0 then
          s
        else
          f (n - 1) (s // { "${name}${toString n}" = (base_conf_by_id n); });
    in f count { };

  # funtion to multiple node based on the same configuration, providing an id to base_conf
  makeMany = base_conf: (makeManyById (id: base_conf));

  # function use to help package development inside composition tree
  # nix-build -E '(import ./nix/helpers.nix).callPackage ./hello {}'
  # or
  # nix build --impure --expr '(import ./nix/helpers.nix).callPackage ./hello {}'
  callPackage = let
    input-pkgs = (import (builtins.fetchTarball
      "https://github.com/edolstra/flake-compat/archive/master.tar.gz") {
        src = ./..;
      }).defaultNix.inputs.nixpkgs;
  in input-pkgs.lib.callPackageWith
  input-pkgs.outputs.legacyPackages.${builtins.currentSystem};
}
