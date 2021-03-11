{ nixpkgs ? <nixpkgs>, system ? builtins.currentSystem, flavour ? "nixos-test"
, composition ? <composition> }:
let

  _composition = if builtins.typeOf composition == "path" then
    import composition
  else
    composition;

  flavours = import ./flavours-meta.nix;

  _flavour_base =
    if builtins.typeOf flavour == "path" then import flavour else flavour;

  _flavour = if builtins.typeOf _flavour_base == "string" then {
    name = _flavour_base;
  } else
    assert builtins.typeOf _flavour_base == "set";
    if flavours ? _flavour_base.name then
      flavours.${_flavour_base.name} // _flavour_base
    else
      _flavour_base;

  nixos_test = import ./nixos-test.nix;
  generate = import ./generate.nix;

in if _flavour.name == "nixos-test" then
  nixos_test { inherit nixpkgs system; } _composition
else if _flavour.name == "nixos-test-driver" then
  (nixos_test { inherit nixpkgs system; } _composition).driver
else
  generate {
    inherit nixpkgs system;
    flavour = _flavour;
  } _composition
