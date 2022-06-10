let helpers = import ./helpers.nix;
in {
  flavours = import ./flavours.nix;
  compose = import ./compose.nix;
  nur = import ./nur.nix;
  setup = import ./setup.nix;
  makeManyById = helpers.makeManyById;
  makeMany = helpers.makeManyById;
  callPackage = helpers.callPackage;
  mapListToAttrs = helpers.mapListToAttrs;
  mapAttrNamesToAttrs = helpers.mapAttrNamesToAttrs;
  mapAttrsToAttrs = helpers.mapAttrsToAttrs;
}
