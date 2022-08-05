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

  overridesNur = nurSet:
     (final: prev:
          let
            overrides = repo:
              builtins.mapAttrs (name: value:
                prev.nur.repos.${repo}.${name}.overrideAttrs
                  (old: helpers.mapAttrsToAttrs (adaptAttr prev) value))
              nurSet.${repo};
          in helpers.mapAttrNamesToAttrs (repo: {
            nur.repos.${repo} = prev.nur.repos.${repo} // (overrides repo);
          }) nurSet);

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

   /*
     [build.options.hello]
     stdenv = "pkgs.gcc8Stdenv" # to override sdtenv=gcc8Stdenv
     stdenv = "pkgs.nur.repos.kapack.fancyStdenv" # to override sdtenv=nur.repos.kapack.fancyStdenv
     option_bool = flase
     option_str = "foo"
   */
  setBuildOptions = prev: options:
    let
      f = n: v:
        let
          path = lib.splitString "." v;
        in
          if (builtins.head path) == "pkgs" then
            lib.getAttrFromPath (lib.drop 1 path) prev
          else
            v;
      in
        builtins.mapAttrs f options;

  buildOptionsNur = nurSet:
    (final: prev:
      let
        buildOptions = repo:
          builtins.mapAttrs (pkg: options:
            {${pkg} = prev.${pkg}.override (setBuildOptions prev options);}) nurSet.${repo};
      in helpers.mapAttrNamesToAttrs (repo: {
            nur.repos.${repo} = prev.nur.repos.${repo} // (buildOptions repo);
          }) nurSet);

  buildOptionsPkg = pkg: options:
    (final: prev:
      {
        ${pkg} = prev.${pkg}.override (setBuildOptions prev options);
      }
    );

  buildOptions = if setupSel ? build.options then
    let
      setBuildOptions = x:
        if (x == "nur") && (nur != null) then
          buildOptionsNur (setupSel.build.options.nur)
        else
          buildOptionsPkg x (setupSel.build.options.${x});
    in
      builtins.map setBuildOptions (builtins.attrNames setupSel.build.options)
  else
    [ ];

  overlays = if nur ? "overlay" then
    # TODO: failed if overrides comes first:  overrides ++ [ nur.overlay ], why ?
    # nur is null before to apply overrides (???), more investigations required
    [ nur.overlay ] ++ overrides ++ buildOptions
  else
    overrides ++ buildOptions;

  params =
    if (setupSel ? "params") && (setupSel ? "override-params") then {
      params = setupSel.params // setupSel."override-params";
    } else
      { };
in setupSel // { inherit overrides overlays; } // params
