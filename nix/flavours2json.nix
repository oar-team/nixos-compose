{ pkgs ? import <nixpkgs> { } }:
let
  flavours = import ./flavours.nix;
  filtered_flavours = let
    filter_flavour = f:
      pkgs.lib.filterAttrs
      (n: v: n == "name" || n == "description" || n == "image") f;
  in pkgs.lib.mapAttrs (n: v: filter_flavour v) flavours;
in rec {
  flavoursJson =
    pkgs.writeText "flavours-link.json" (builtins.toJSON filtered_flavours);
  showFlavours = pkgs.writeScriptBin "showFlavours" ''
    cat ${flavoursJson} | ${pkgs.jq}/bin/jq
  '';
}
