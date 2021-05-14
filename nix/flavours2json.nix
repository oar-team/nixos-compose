# To use
# nix-build flavours2json.nix --out-link flavours-link.json && cp -f flavours-link.json flavours.json
#
{ pkgs ? import <nixpkgs> { } }:
let
  flavours = import ./flavours.nix;
  filtered_flavours =
    pkgs.lib.filterAttrsRecursive (n: v: n != "extraModule") flavours;
in pkgs.writeText "flavours-link.json" (builtins.toJSON filtered_flavours)
