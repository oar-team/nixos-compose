{ nixpkgs, system, extraConfigurations ? [ ], ... }:
composition:
let
  pkgs = import nixpkgs { inherit system; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";
  testingPython = import "${modulesPath}/lib/testing-python.nix" {
    inherit system extraConfigurations;
  };
in testingPython.makeTest (composition { inherit pkgs lib modulesPath; })
