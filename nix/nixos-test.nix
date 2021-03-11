{ nixpkgs, system, ... }:
composition:
let
  testingPython = import "${toString nixpkgs}/nixos/lib/testing-python.nix" {
    inherit system;
  };
in testingPython.makeTest (composition { pkgs = (import nixpkgs) { }; })
