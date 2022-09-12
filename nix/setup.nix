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
#   # src, args, deps, attrs
#   # Limited to src attribut, use overlay in flake.nix for other attributs
#   TODO: add compilation option
#
#   # to override hello's to local directoy
#   [dev.build.hello]
#   src = "/home/auguste/hello"
#
#   [dev.build.hello.src.fetchurl]
#   # to overdrive src attribut of nixpkgs src
#   url = "mirror://gnu/hello/hello-2.8.tar.gz"
#   sha256 = "sha256-5rd/gffPfa761Kn1tl3myunD8TuM+66oy1O7XqVGDXM="
#
#
#   [build.nur.repos.kapack]
#   oar = { src = "/home/auguste/dev/oar3" }
#
#   [dev.build.nur.repos.kapack.oar.src.fetchFromGitHub]
#   owner = "mpoquet"
#   repo = "oar3"
#   rev = "d26d660ad2d9cfbd2a8477019c8c5fd0f353431b"
#   sha256 = "sha256-Bl1J6ZZYoD8/zni8GU0fSKJPj9j/IRW7inZ8GQ7Di10="
#
#
#   TODO remove overrides ?
#
#   [dev.overrides.nur.kapack.oar.src.fetchFromGitHub]
#   owner = "mpoquet"
#   repo = "oar3"
#   rev = "d26d660ad2d9cfbd2a8477019c8c5fd0f353431b"
#   sha256 = "sha256-Bl1J6ZZYoD8/zni8GU0fSKJPj9j/IRW7inZ8GQ7Di10="
#
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
    lib.recursiveUpdate setupRaw {project = { selected = "";};};

  helpers = import ./helpers.nix;

  adaptAttr = prev: attrName: value: {
    ${attrName} = (if (attrName == "src") then
      if (builtins.isString value) then
        /. + value
      else if (builtins.isAttrs value) then
        let fetchFunction = builtins.head (builtins.attrNames value);
        in prev.${fetchFunction} value.${fetchFunction}
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
    (final: prev: {
      ${pkgsToOverride} = prev.${pkgsToOverride}.overrideAttrs
        (old: helpers.mapAttrsToAttrs (adaptAttr prev) value);
    });

  overrides = if setupSel ? "overrides" then
    let
      setOverrides = x:
        if (x == "nur") && (nur != null) then
          overridesNur (setupSel.overrides.nur)
        else
          overridePkg x (setupSel.overrides.${x});
    in builtins.map setOverrides (builtins.attrNames setupSel.overrides)
  else
    [ ];

  #
  # Build's Parametrization
  #

  setSrcAttr = prev: src: {
    src = (if (builtins.isString src) then
      /. + src
    else
      let fetchFunction = builtins.head (builtins.attrNames src);
      in prev.${fetchFunction} src.${fetchFunction});
  };

  getBuildDeps = prev: deps:
    #TODO: add assert to deps exist in prev ???
    builtins.mapAttrs (n: x: lib.getAttrFromPath (lib.splitString "." x) prev)
    deps;

  lookupOverlayPkgFunc = {
    deps = pkgOverrideDeps;
    args = pkgOverrideArgs;
    src = pkgOverrideSrc;
    attrs = pkgOverrideAttrs;
  };

  pkgOverrideDeps = pkg: op_args:
    (final: prev: {
      ${pkg} = prev.${pkg}.override (getBuildDeps prev op_args);
    });

  # TODO: Not tested
  pkgOverrideArgs = pkg: op_args:
    (final: prev: { ${pkg} = prev.${pkg}.override op_args; });

  pkgOverrideSrc = pkg: src:
    (final: prev: {
      ${pkg} = prev.${pkg}.overrideAttrs (old: (setSrcAttr prev src));
    });

  # TODO to test
  pkgOverrideAttrs = pkg: op_args:
    (final: prev: { ${pkg} = prev.${pkg}.overrideAttrs (old: op_args); });

  buildOverlayPkg = pkg: v:
    builtins.map (op:
      assert lib.assertOneOf "setup.toml: build operation" op [
        "deps"
        "args"
        "src"
        "attrs"
      ];
      (lookupOverlayPkgFunc.${op}) pkg v.${op}) (builtins.attrNames v);

  #
  # Build's Parametrization Nur part
  #

  lookupOverlayNurPkgFunc = {
    deps = nurPkgOverrideDeps;
    args = nurPkgOverrideArgs;
    src = nurPkgOverrideSrc;
    attrs = nurPkgOverrideAttrs;
  };

  nurPkgOverrideDeps = repo: pkg: op_args:
    (final: prev:
      let
        overridesArgs = {
          ${pkg} =
            prev.nur.repos.${repo}.${pkg}.override (getBuildDeps prev op_args);
        };
      in { nur.repos.${repo} = prev.nur.repos.${repo} // overridesArgs; });

  nurPkgOverrideArgs = repo: pkg: op_args:
    (final: prev:
      let
        overridesArgs = {
          ${pkg} = prev.nur.repos.${repo}.${pkg}.override op_args;
        };
      in { nur.repos.${repo} = prev.nur.repos.${repo} // overridesArgs; });

  nurPkgOverrideSrc = repo: pkg: src:
    (final: prev:
      let
        overridesAttrs = {
          ${pkg} = prev.nur.repos.${repo}.${pkg}.overrideAttrs
            (old: (setSrcAttr prev src));
        };
      in { nur.repos.${repo} = prev.nur.repos.${repo} // overridesAttrs; });

  nurPkgOverrideAttrs = repo: pkg: op_args:
    (final: prev:
      let
        overridesAttrs = {
          ${pkg} = prev.nur.repos.${repo}.${pkg}.overrideAttrs (old: op_args);
        };
      in { nur.repos.${repo} = prev.nur.repos.${repo} // overridesAttrs; });

  buildOverlayNurPkg = repo: pkg: v:
    builtins.map (op:
      assert lib.assertOneOf "setup.toml: build (nur) operation" op [
        "deps"
        "args"
        "src"
        "attrs"
      ];
      (lookupOverlayNurPkgFunc.${op}) repo pkg v.${op}) (builtins.attrNames v);

  buildOverlayNur = nurReposPkgs:
    let
      repos = builtins.attrNames nurReposPkgs;
      build_overlay = repo: pkg:
        buildOverlayNurPkg repo pkg nurReposPkgs.${repo}.${pkg};
    in builtins.map (repo:
      builtins.map (pkg: build_overlay repo pkg)
      (builtins.attrNames nurReposPkgs.${repo})) repos;

  buildOverlays = if setupSel ? build then
    let
      build_overlay = x:
        if (x == "nur") && (nur != null) then
          buildOverlayNur (setupSel.build.nur.repos)
        else
          buildOverlayPkg x (setupSel.build.${x});
    in lib.flatten
    (builtins.map build_overlay (builtins.attrNames setupSel.build))
  else
    [ ];

  overlays = if nur ? "overlay" then
  # TODO: failed if buildOverlays comes first: buildOverlays ++ [ nur.overlay ], why ?
  # nur is null before to apply buildOverlays (???), more investigations are required
    [ nur.overlay ] ++ overrides ++ buildOverlays
  else
    overrides ++ buildOverlays;

  params = if (setupSel ? "params") && (setupSel ? "override-params") then {
    params = setupSel.params // setupSel."override-params";
  } else
    { };
in setupSel // { inherit overrides overlays; } // params
