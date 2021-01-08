{ pkgs ? import <nixpkgs> {} }:
let
  nixosComposeEnv = pkgs.poetry2nix.mkPoetryEnv {
    projectDir = ./.;
    editablePackageSources = {
      nixos-compose = ./nixos-compose;
    };
  };
in
pkgs.mkShell {
  buildInputs = [ nixosComposeEnv pkgs.poetry pkgs.openssh ];
}
