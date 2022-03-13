{ nixpkgs, system, setup, nur ? { }, overlays ? [ ], extraConfigurations ? [ ], ... }:
composition:
let
  pkgs = import nixpkgs { inherit system overlays; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";
  testingPython = import "${toString modulesPath}/lib/testing-python.nix" {
    inherit pkgs system extraConfigurations;
  };
in testingPython.makeTest (composition { inherit pkgs lib modulesPath setup nur; })
