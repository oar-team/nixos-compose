{ nixpkgs, pkgs ? null, system ? builtins.currentSystem, flavour ? null
, composition ? null, single_composition_name ? "composition"
, compositions ? null, flavours ? null, overlays ? [ ], setup ? { }
, extraConfigurations ? [ ], nur ? { } }:
let
  builtin_flavours = import ./flavours.nix;
  _composition = if builtins.typeOf composition == "path" then
    import composition
  else if composition != null then
    composition
  else if builtins.pathExists ../composition.nix then
    import ../composition.nix
  else
    null;

  _compositions = assert _composition != null || compositions != null;
    if compositions != null then
      if builtins.typeOf compositions == "path" then
        import compositions
      else
        compositions
    else {
      "${single_composition_name}" = _composition;
    };

  _flavours = if builtins.typeOf flavours == "path" then
    import flavours
  else if builtins.typeOf flavours == "set" then
    flavours
  else if compositions != null then
    if flavours == null then builtin_flavours else flavours

  else if flavour != null then
    let
      _flavour_base =
        if builtins.typeOf flavour == "path" then import flavour else flavour;
    in if builtins.typeOf _flavour_base == "string" then
      assert builtin_flavours ? ${_flavour_base}; {
        ${_flavour_base} = builtin_flavours.${_flavour_base};
      }
    else
      assert builtins.typeOf _flavour_base == "set";
      if builtin_flavours ? _flavour_base.name then
        builtin_flavours.${_flavour_base.name} // _flavour_base
      else
        _flavour_base
  else
    builtin_flavours;

  compositions_names = builtins.attrNames _compositions;
  nb_compositions = builtins.length compositions_names;
  flavours_names = builtins.attrNames _flavours;

  _overlays = if builtins.hasAttr "overlays" _setup then
    overlays ++ _setup.overlays
  else
    overlays;

  # overlays must be injected via (extra)config and pkgs' overlays parametrer (see nixos-test.nix)
  # Two pkgs exploitations in composition, same pkgs but used differently
  # {pkgs, ... }: {
  #    nodes = {
  #       foo = {pkgs, ... }:
  _extraConfigurations = extraConfigurations
    ++ [{ nixpkgs.overlays = _overlays; }];

  _setup =
    let lib = if pkgs != null then pkgs.lib else (import nixpkgs { }).lib;
    in import ./setup.nix setup { inherit lib nur; };

  f = composition_name: flavour_name: composition: flavour: {
    name = (composition_name + "::" + flavour_name);
    value = ((import ./one_composition.nix) {
      inherit nixpkgs system overlays nur flavour composition_name composition;
      extraConfigurations = _extraConfigurations;
      setup = _setup;
    });
  };

  f_multiple_compositions = flavour: {
    name = "::${flavour.name}";
    value = ((import ./multiple_compositions.nix) {
      inherit nixpkgs system flavour nur compositions;
      overlays = _overlays;
      extraConfigurations = _extraConfigurations;
      setup = _setup;
    });
  };

  multiple_compositions_flavours = nixpkgs.lib.filterAttrs (n: v:
    v ? image && v.image ? distribution && v.image.distribution == "all-in-one")
    _flavours;

in (builtins.listToAttrs (nixpkgs.lib.flatten (map (composition_name:
  (map (flavour_name:
    let
      selected_flavour = builtins.getAttr flavour_name _flavours;
      composition = builtins.getAttr composition_name _compositions;
    in (f composition_name flavour_name composition selected_flavour))
    flavours_names)) compositions_names)) // (if nb_compositions == 1 then
      { }
    else
      (nixpkgs.lib.mapAttrs' (name: flavour_: f_multiple_compositions flavour_)
        multiple_compositions_flavours)))
// (import ./flavours2json.nix { pkgs = nixpkgs.legacyPackages.${system}; })
