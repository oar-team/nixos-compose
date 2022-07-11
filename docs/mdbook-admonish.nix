{ lib, stdenv, fetchFromGitHub, rustPlatform }:

rustPlatform.buildRustPackage rec {
  pname = "mdbook-admonish";
  version = "1.7.0";

  src = fetchFromGitHub {
    owner = "tommilligan";
    repo = pname;
    rev = "v${version}";
    sha256 = "sha256-AGOq05NevkRU8qHsJIWd2WfZ4i7w/wexf6c0fUAaoLg=";
  };

  cargoSha256 = "sha256-v7MGJlDm5nvydjFAZZS94afZY2OVUjJQ9eXYaY9JxBs=";
}