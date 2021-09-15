# To use
# nix-build flavours2json.nix --out-link flavours-link.json && cp -f flavours-link.json flavours.json
#
{ pkgs ? import <nixpkgs> { } }:
let
  flavours = import ./flavours.nix;
  filtered_flavours = let
    filter_flavour = f:
      pkgs.lib.filterAttrs
      (n: v: n == "name" || n == "description" || n == "image") f;
  in pkgs.lib.mapAttrs (n: v: filter_flavour v) flavours;
in pkgs.writeText "flavours-link.json" (builtins.toJSON filtered_flavours)
