file:
{ lib, nur ? { }, }:
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
  setupSel = if (setupRaw ? "project") && (setupRaw.project ? "selected") then
    assert builtins.hasAttr setupRaw.project.selected setupRaw;
    lib.recursiveUpdate setupRaw setupRaw.${setupRaw.project.selected}
  else
    setupRaw;

  helpers = import ./helpers.nix;

  adaptAttr = attrName: value: {
    ${attrName} = (if (attrName == "src") && (builtins.isString value) then
      /. + value
    else
      value);
  };

  overrides = if setupSel ? "overrides" then
    if (setupSel.overrides ? "nur") && (nur != null) then
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
  overlays = if nur ? "overlay" then
    # TODO: failed if overrides comes first:  overrides ++ [ nur.overlay ], why ?
    # nur is null before to apply overrides (???), more investigations required
    [ nur.overlay ] ++ overrides
  else
    overrides;

  params =
    if (setupSel ? "params") && (setupSel ? "override-params") then {
      params = setupSel.params // setupSel."override-params";
    } else
      { };
in setupSel // { inherit overrides overlays; } // params
