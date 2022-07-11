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

  # mapListToAttrs (o: {${o}=o+"-2";}) [ "a" "b"]
  # { a = "a-2"; b = "b-2"; }
  mapListToAttrs = op: list:
    let
      len = builtins.length list;
      g = n: s:
        if n == len then s else g (n + 1) (s // (op (builtins.elemAt list n)));
    in g 0 { };

  # mapAttrNamesToAttrs (o: {${o}=o+"-2";}) { a = 1; b = 2; }
  # { a = "a-2"; b = "b-2"; }
  mapAttrNamesToAttrs = op: attrs: mapListToAttrs op (builtins.attrNames attrs);

  # mapAttrsToAttrs (n: v: {${n+"2"}=1+v;}) { a = 1; b = 2; }
  # { a2 = 2; b2 = 3; }
  mapAttrsToAttrs = op: attrs:
    let
      list = builtins.attrNames attrs;
      len = builtins.length list;
      g = n: s:
        if n == len then
          s
        else
          let
            attrName = builtins.elemAt list n;
            value = attrs.${attrName};
          in g (n + 1) (s // (op attrName value));
    in g 0 { };

}
