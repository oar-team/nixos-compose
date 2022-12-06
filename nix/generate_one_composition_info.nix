{ pkgs, flavour, modulesPath, system, setup, extraConfigurations, nur, helpers
, baseConfig ? false, ... }:
{ compositionName ? "", composition ? { } }:

let
  lib = pkgs.lib;
  compositionSet = composition {
    inherit pkgs lib system modulesPath helpers flavour setup nur;
  };

  roles = if compositionSet ? roles then compositionSet.roles else compositionSet.nodes;
  flavourConfig = if flavour ? module then flavour.module else { };

  buildOneconfig = role: configuration:
    import "${modulesPath}/lib/eval-config.nix" {
      inherit system;
      modules = [
        {
          environment.etc."nxc-composition" = {
            mode = "0644";
            text = "${compositionName}";
          };
        }
        {system.stateVersion = lib.mkDefault lib.trivial.release;} # perhaps a better place exist than here
        configuration
        flavourConfig
      ] ++ extraConfigurations;
    };

in let
  allConfig = pkgs.lib.mapAttrs buildOneconfig roles;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${if compositionSet ? testScript then compositionSet.testScript else ""}";
  };

  # only rolesDistribution, could be extended
  optionalCompositionAttr = if compositionSet ? rolesDistribution then
    { roles_distribution = compositionSet.rolesDistribution; }
                            else {};

  imageInfo = if flavour.image ? distribution && flavour.image.distribution
  == "all-in-one" then
    import ./all-in-one.nix {
      inherit pkgs flavour compositionName allConfig buildOneconfig;
    }
  else {
    roles =
      pkgs.lib.mapAttrs (n: m: m.config.system.build.ramdiskInfo) allConfig;
  };
  # pkgs.writeText "compose-info.json" (builtins.toJSON ({
  #  test_script = testScriptFile;
  #  flavour = pkgs.lib.filterAttrs (n: v: n != "extraModule") flavour;
  #} // imageInfo))
in if baseConfig then
  buildOneconfig "" { }
else
  { test_script = testScriptFile; } // optionalCompositionAttr // imageInfo
