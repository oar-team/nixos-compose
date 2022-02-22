file:
{ nur ? null }:
#
# In flake.nix:
#   setup = nxc.lib.setup ./setup.toml { inherit nur; };
#   ...
#   { nixpkgs.overlays = [ nur.overlay ] ++ setup.overrides; }
#
# In setup.toml:
#   [overrides.nur.kapack]
#   oar = { src = "/home/auguste/dev/oar3" }
#
let
  setup = builtins.fromTOML (builtins.readFile file);

  helpers = import ./helpers.nix;

  adaptAttr = attrName: value: {
    ${attrName} = (if (attrName == "src") && (builtins.isString value) then
      /. + value
    else
      value);
  };
in {
  overrides = if builtins.hasAttr "overrides" setup then
    if (builtins.hasAttr "nur" setup.overrides) && (nur != null) then
      [
        (self: super:
          let
            overrides = repo:
              builtins.mapAttrs (name: value:
                super.nur.repos.${repo}.${name}.overrideAttrs
                (old: helpers.mapAttrsToAttrs adaptAttr value))
              setup.overrides.nur.${repo};
          in helpers.mapAttrNamesToAttrs (repo: {
            nur.repos.${repo} = super.nur.repos.${repo} // (overrides repo);
          }) setup.overrides.nur)
      ]
    else
      [ ]
  else
    [ ];
}
