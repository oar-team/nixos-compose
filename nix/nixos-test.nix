{ nixpkgs, system, ... }:
composition:
let
  pkgs = import nixpkgs { };
  lib = pkgs.lib;
  testingPython = import "${toString nixpkgs}/nixos/lib/testing-python.nix" {
    inherit system;
  };
in testingPython.makeTest (composition { inherit pkgs lib; })
