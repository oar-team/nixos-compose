{ nixpkgs, mode, ... }:
composition:
let
  pkgs = (import nixpkgs) { };
  testingPython = import "${toString nixpkgs}/nixos/lib/testing-python.nix" {
    inherit pkgs;
    system = builtins.currentSystem;
  };
in testingPython.makeTest (composition { pkgs = pkgs; })
