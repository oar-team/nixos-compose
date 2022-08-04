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
#
#   # Overrides are added to overlays
#   # Limited to src attribut, use overlay in flake.nix for other attributs
#   TODO: add compilation option
#
#   [overrides.nur.kapack]
#   oar = { src = "/home/auguste/dev/oar3" }
#
#   [dev.overrides.nur.kapack.oar.src.fetchFromGitHub]
#   owner = "mpoquet"
#   repo = "oar3"
#   rev = "d26d660ad2d9cfbd2a8477019c8c5fd0f353431b"
#   sha256 = "sha256-Bl1J6ZZYoD8/zni8GU0fSKJPj9j/IRW7inZ8GQ7Di10="
#
#   [dev.overrides.hello.src.fetchurl]
#   # to overdrive src attribut of nixpkgs src
#   url = "mirror://gnu/hello/hello-2.8.tar.gz"
#   sha256 = "sha256-5rd/gffPfa761Kn1tl3myunD8TuM+66oy1O7XqVGDXM="
#
#   # to override hello's to local directoy
#   [dev.overrides.hello]
#   src = "/home/auguste/hello"
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

  adaptAttr = prev: attrName: value: {
    ${attrName} = (if (attrName == "src") then
      if (builtins.isString value) then
        /. + value
      else
        if (builtins.isAttrs value) then
          let
            fetchFunction =  builtins.head (builtins.attrNames value);
          in
            prev.${fetchFunction} value.${fetchFunction}
        else
          #TODO raise error
          value
    else
      value);
  };

  overridesNur = nurToOverride:
     (final: prev:
          let
            overrides = repo:
              builtins.mapAttrs (name: value:
                prev.nur.repos.${repo}.${name}.overrideAttrs
                  (old: helpers.mapAttrsToAttrs (adaptAttr prev) value))
              nurToOverride.${repo};
          in helpers.mapAttrNamesToAttrs (repo: {
            nur.repos.${repo} = prev.nur.repos.${repo} // (overrides repo);
          }) nurToOverride); #setupSel.overrides.nur)

  overridePkg = pkgsToOverride: value:
    (final: prev:
      {
        ${pkgsToOverride} = prev.${pkgsToOverride}.overrideAttrs (old:  helpers.mapAttrsToAttrs (adaptAttr prev) value);
      }
    );
  overrides = if setupSel ? "overrides" then
    let
      setOverrides = x:
        if (x == "nur") && (nur != null) then
          overridesNur (setupSel.overrides.nur)
        else
          overridePkg x (setupSel.overrides.${x});
    in
      builtins.map setOverrides (builtins.attrNames setupSel.overrides)
  else
    [ ];

  # TODO: add compilation option


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
