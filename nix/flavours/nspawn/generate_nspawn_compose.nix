{ nixpkgs, system, flavour, overlays ? [ ], setup ? { }, nur ? { }, extraConfigurations ? [ ]
,helpers, ... }:
composition:

let
  pkgs = (import nixpkgs) { inherit system overlays; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";

  roleConfigWithoutVirtualisation = configRole:
    args@{ pkgs, ... }:
    removeAttrs
      (if lib.isFunction configRole then configRole args else configRole)
      [ "virtualisation" ];

  buildOneconfig = roleName: roleConfig:
    pkgs.nixos {
      imports = [
        (import ./base.nix roleName)
        (roleConfigWithoutVirtualisation roleConfig)
        { _module.args.nodes = nodes; }
        { system.stateVersion = lib.mkDefault lib.trivial.release; }
      ] ++ extraConfigurations;
    };

  # FIXME: extract the common part in future refactor
  # see `nix/generate_one_composition_info.nix` for the fixed-point rationale
  nodes = lib.mapAttrs (_: c: c.config // { config = c.config; }) allConfig;

  compositionSet =
    if lib.isFunction composition then
      composition { inherit pkgs lib system modulesPath helpers flavour setup nur nodes; }
    else
      composition;

  roles = if compositionSet ? roles then compositionSet.roles else compositionSet.nodes;

  allConfig = lib.mapAttrs buildOneconfig roles;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${if compositionSet ? testScript then compositionSet.testScript else ""}";
  };

  # only rolesDistribution, could be extended
  optionalCompositionAttr = if compositionSet ? rolesDistribution then
    { roles_distribution = compositionSet.rolesDistribution; }
                            else {};

  extraVolumes =
    if compositionSet ? extraVolumes then compositionSet.extraVolumes else [ ];

  nspawnPorts =
    if compositionSet ? nspawnPorts then compositionSet.nspawnPorts else { };

  nspawnComposition = lib.mapAttrs (roleName: _:
    let
      builtConfig = allConfig.${roleName};
    in {
      toplevel = "${builtConfig.toplevel}";
      init =  "${builtConfig.toplevel}/init";
      volumes = extraVolumes;
      ports =
        if nspawnPorts ? "${roleName}" then nspawnPorts."${roleName}" else [ ];
    }) roles;

in pkgs.writeTextFile {
  name = "compose-info.json";
  text = builtins.toJSON ({
    roles = builtins.attrNames roles;
    composition = nspawnComposition;
    test_script = testScriptFile;
    flavour = flavour.name;
  } // optionalCompositionAttr );
}
