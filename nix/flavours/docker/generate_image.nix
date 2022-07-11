{ pkgs ? import <nixpkgs> { }, name ? "nxc-docker-base-image", tag ? "latest"
, ... }:

let
  # Taken from Arion
  # TODO: is it necessary ?
  minContents = pkgs.runCommand "minimal-contents" { } ''
    mkdir -p $out/bin $out/usr/bin
    ln -s /run/system/bin/sh $out/bin/sh
    ln -s /run/system/usr/bin/env $out/usr/bin/env
  '';

  # Creating the base image for the containers
  baseImage = pkgs.dockerTools.buildImage {
    inherit name tag;
    extraCommands = ''
      export NIX_REMOTE=local?root=$PWD
    '';
    contents = [
      minContents
      # TODO: required ?
      pkgs.nix
    ];
  };
in baseImage
