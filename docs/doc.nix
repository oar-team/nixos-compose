{ nixpkgs, pkgs, system }:
let
  mdbook-admonish =
    nixpkgs.legacyPackages.${system}.callPackage ./mdbook-admonish.nix { };
  buildInputs = with pkgs; [ mdbook mdbook-mermaid mdbook-admonish ]; # mdbook-linkcheck pour checker la validiter des liens
  flakeImage = pkgs.dockerTools.pullImage {
    imageName = "nixpkgs/nix-flakes";
    imageDigest =
      "sha256:653ac11d23bbe5b9693f156cafeb97c7e8000b187d1bafec3798f6c92238fde2";
    sha256 = "15543hvgw2g8aadkx335pprrxq3ldcv93a9qq9c4am0rbkw8prrw";
    finalImageName = "nixpkgs/nix-flakes";
    finalImageTag = "nixos-21.11";
  };
in rec {
  doc = pkgs.stdenv.mkDerivation {
    name = "nxcDoc";
    src = ../docs;
    nativeBuildInputs = buildInputs;
    buildCommand = ''
      mkdir $out
      cp -r --no-preserve=mode $src/* .
      mdbook build -d $out
    '';
  };

  imageCIdoc = pkgs.dockerTools.buildImageWithNixDb {
    name = "registry.gitlab.inria.fr/nixos-compose/nixos-compose";
    tag = "doc";
    fromImage = flakeImage;
    copyToRoot = buildInputs;
  };
}
