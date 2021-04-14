{ nixpkgs, system, compositions, flavours, extraConfigurations ? [ ] }:
let
  compositions_names = builtins.attrNames compositions;
  flavours_names = builtins.attrNames flavours;

  f = composition_name: flavour_name: composition: flavour: {
    name = (composition_name + "_" + flavour_name);
    value = ((import ./compose.nix) {
      inherit nixpkgs system extraConfigurations flavour composition;
    });
  };

in builtins.listToAttrs (nixpkgs.lib.flatten (map (composition_name:
  (map (flavour_name:
    let
      flavour = builtins.getAttr flavour_name flavours;
      composition = builtins.getAttr composition_name compositions;
    in (f composition_name flavour_name composition flavour)) flavours_names))
  compositions_names))
