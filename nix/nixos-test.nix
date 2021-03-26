{ nixpkgs, system, extraConfigurations ? [ ], ... }:
composition:
let
  pkgs = import nixpkgs { inherit system; };
  lib = pkgs.lib;
  testingPython = import "${toString nixpkgs}/nixos/lib/testing-python.nix" {
    inherit system extraConfigurations;
  };
in testingPython.makeTest (composition { inherit pkgs lib; })
