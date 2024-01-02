{ nixpkgs, system, flavour, overlays ? [ ], setup ? { }, nur ? { }, extraConfigurations ? [ ]
,helpers, ... }:
composition:

let
  pkgs = (import nixpkgs) { inherit system overlays; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";
  compositionSet = composition { inherit pkgs lib system modulesPath helpers flavour setup nur; };

  roles = if compositionSet ? roles then compositionSet.roles else compositionSet.nodes;

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

  nspawnComposition = builtins.mapAttrs (roleName: roleConfig:
    let
      roleConfigWithoutVirtualisation = configRole:
        args@{ pkgs, ... }:
        builtins.removeAttrs (configRole args) [ "virtualisation" ];
      config = {
        system.stateVersion = lib.mkDefault lib.trivial.release;
        imports = [ (import ./base.nix roleName)  (roleConfigWithoutVirtualisation roleConfig) ]
          ++ extraConfigurations;
      };
      builtConfig = pkgs.nixos config;
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
