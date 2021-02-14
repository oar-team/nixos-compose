flavourOptions: composition:

let

  flavours = {
    vm = {
      name = "vm";
      vm = true;
      image = {
        type = "ramdisk";
        distribution = "all-in-one";
      };
    };
  };

  nixpkgs =
    if flavourOptions ? nixpkgs then flavourOptions.nixpkgs else flavourOptions;

  flavour = if flavourOptions ? nixpkgs then
    if flavourOptions ? name then
      if flavours ? "${flavourOptions.name}" then
        flavours."${flavourOptions.name}" // flavourOptions
      else
        flavourOptions
    else
      "nixos-test"
  else
    "nixos-test";

  f = if flavour == "nixos-test"
  || (flavour ? name && flavour.name == "nixos-test") then
    import ./nixos-test.nix
  else
    import ./generate.nix;
in f { inherit nixpkgs flavour; } composition
