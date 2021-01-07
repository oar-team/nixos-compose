flavour: composition:

let

  modes = {
    vm = {
      name = "vm";
      vm = true;
      initrd = "all-in-one";
    };
  };

  nixpkgs = if flavour ? nixpkgs then flavour.nixpkgs else flavour;

  mode = if flavour ? nixpkgs then
    if flavour ? mode then
      if builtins.isAttrs flavour.mode then
        flavour.mode
      else
        modes."${flavour.mode}"
    else
      "nixos-test"
  else
    "nixos-test";

  f = if mode == "nixos-test" then
    import ./nixos-test.nix
  else
    import ./generate.nix;
in f { inherit nixpkgs mode; } composition
