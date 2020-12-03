flavour: composition:

let
  nixpkgs = if flavour ? nixpkgs then flavour.nixpkgs else flavour;

  mode = if flavour ? nixpkgs then
    if flavour ? mode then flavour.mode else "nixos-test"
  else
    "nixos-test";

  f = if mode == "nixos-test" then import ./nixos-test.nix else import ./kexec-vm.nix;
in f { inherit nixpkgs mode; } composition
