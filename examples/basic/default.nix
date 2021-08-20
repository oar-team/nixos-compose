{ system ? builtins.currentSystem, flavour ? "nixos-test" }:
let
  nixpkgs = builtins.fetchTarball {
    url =
      "https://github.com/NixOS/nixpkgs/archive/e9bdaba31748dc5d9f78c280f2582017b6bf0dd9.tar.gz";
    sha256 = "1rgkgir0l6m50yf0aih43ih4hs62f532yssg1xfa3j8v5pshsa6v";
  };
in (import ./nix/compose.nix) { inherit nixpkgs system flavour; }
