{ nixpkgs ? <nixpkgs>, system ? builtins.currentSystem, flavour ? "nixos-test"
, composition ? import ../composition.nix, extraConfigurations ? [ ] }:
let

  _composition = if builtins.typeOf composition == "path" then
    import composition
  else
    composition;

  flavours = import ./flavours.nix;

  _flavour_base =
    if builtins.typeOf flavour == "path" then import flavour else flavour;

  _flavour = if builtins.typeOf _flavour_base == "string" then
    assert flavours ? ${_flavour_base}; flavours.${_flavour_base}
  else
    assert builtins.typeOf _flavour_base == "set";
    if flavours ? _flavour_base.name then
      flavours.${_flavour_base.name} // _flavour_base
    else
      _flavour_base;

  nixos_test = import ./nixos-test.nix;
  generate = import ./generate.nix;
  generate_docker_compose = import ./generate_docker_compose.nix;

in if _flavour.name == "nixos-test" then
  nixos_test { inherit nixpkgs system extraConfigurations; } _composition
else if _flavour.name == "nixos-test-driver" then
  (nixos_test { inherit nixpkgs system extraConfigurations; }
    _composition).driver
else if _flavour.name == "nixos-test-ssh" then
  (nixos_test {
    inherit nixpkgs system;
    extraConfigurations = extraConfigurations ++ [ ./base.nix ];
  } _composition).driver
else if _flavour.name == "docker" then
  generate_docker_compose {
    inherit nixpkgs system extraConfigurations;
  } _composition
else
  generate {
    inherit nixpkgs system extraConfigurations;
    flavour = _flavour;
  } _composition
