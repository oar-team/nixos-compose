file:
{ NUR ? { }, nur ? { }, }:
#
# In flake.nix:
#   packages.${system} = nxc.lib.compose {
#     inherit nixpkgs system;
#     setup = ./setup.toml;
#     composition = ./composition.nix;
#   };
#
# In setup.toml:
#   [project]
#   [params]
#   # a="hello world"
#   # b=10
#   # overrides are added to overlays
#   [overrides.nur.kapack]
#   oar = { src = "/home/auguste/dev/oar3" }
#
# Complete example in nix/examples/setup directory
#
let
  setupRaw = builtins.fromTOML (builtins.readFile file);
  # TODO: add assert to avoid use of reserved keywords as setup variant
  # (i.e. project, options, params, overrides, override-params)
  setupSel = if (builtins.hasAttr "project" setupRaw)
  && (builtins.hasAttr "selected" setupRaw.project) then
    assert builtins.hasAttr setupRaw.project.selected setupRaw;
    setupRaw // setupRaw.${setupRaw.project.selected}
  else
    setupRaw;

  helpers = import ./helpers.nix;

  adaptAttr = attrName: value: {
    ${attrName} = (if (attrName == "src") && (builtins.isString value) then
      /. + value
    else
      value);
  };

  overrides = if builtins.hasAttr "overrides" setupSel then
    if (builtins.hasAttr "nur" setupSel.overrides) && (nur != null) then
      [
        (self: super:
          let
            overrides = repo:
              builtins.mapAttrs (name: value:
                super.nur.repos.${repo}.${name}.overrideAttrs
                (old: helpers.mapAttrsToAttrs adaptAttr value))
              setupSel.overrides.nur.${repo};
          in helpers.mapAttrNamesToAttrs (repo: {
            nur.repos.${repo} = super.nur.repos.${repo} // (overrides repo);
          }) setupSel.overrides.nur)
      ]
    else
      [ ]
  else
    [ ];
  overlays = if builtins.hasAttr "overlay" nur then
    overrides ++ [ nur.overlay ]
  else if builtins.hasAttr "overlay" NUR then
    overrides ++ [ NUR.overlay ]
  else
    overrides;

  params = if (builtins.hasAttr "params" setupSel)
  && (builtins.hasAttr "override-params" setupSel) then {
    params = setupSel.params // setupSel."override-params";
  } else
    { };
in setupSel // { inherit overrides overlays; } // params
