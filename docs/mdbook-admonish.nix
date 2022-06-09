{ lib, stdenv, fetchFromGitHub, rustPlatform }:

rustPlatform.buildRustPackage rec {
  pname = "mdbook-admonish";
  version = "1.4.1";

  src = fetchFromGitHub {
    owner = "tommilligan";
    repo = pname;
    rev = "v${version}";
    sha256 = "sha256-7poBCVJ+bE0XRpOnNMTXvL5TghTlgeeBOXZlysOr7fU=";
  };

  cargoSha256 = "sha256-fesYQvKDR2o1AcqHLRK/eQonQfUaD+dBz9EOFdf8FBg=";
}