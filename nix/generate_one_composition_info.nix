{ pkgs, flavour, modulesPath, system, setup, extraConfigurations, nur, helpers
, baseConfig ? false, ... }:
{ compositionName ? "", composition ? { } }:

let
  lib = pkgs.lib;
  compositionSet = composition {
    inherit pkgs lib system modulesPath helpers flavour setup nur;
  };
  nodes = compositionSet.nodes;
  testScriptRaw =
    if compositionSet ? testScript then compositionSet.testScript else "";
  machines = builtins.attrNames nodes;

  # from nixpkgs/nixos/lib/testing-python.nix
  testScript =
    # Call the test script with the computed nodes.
    if pkgs.lib.isFunction testScriptRaw then
      testScriptRaw { inherit nodes; }
    else
      testScriptRaw;

  vmSharedDirMod = { lib, config, ... }: {
    options = {
      vm-shared-dir = { enable = lib.mkEnableOption "a vm shared directory"; };
    };
    config = lib.mkIf config.vm-shared-dir.enable {
      fileSystems."/tmp/shared" = {
        device = "shared";
        fsType = "9p";
        options = [ "trans=virtio" "version=9p2000.L" ];
      };
    };
  };

  flavourConfig = if flavour ? module then flavour.module else { };

  buildOneconfig = machine: configuration:
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
        vmSharedDirMod
        flavourConfig

      ] ++ extraConfigurations;
    };

in let
  allConfig = pkgs.lib.mapAttrs buildOneconfig nodes;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${testScript}";
  };

  imageInfo = if flavour.image ? distribution && flavour.image.distribution
  == "all-in-one" then
    import ./all-in-one.nix {
      inherit pkgs flavour compositionName allConfig buildOneconfig;
    }
  else {
    nodes =
      pkgs.lib.mapAttrs (n: m: m.config.system.build.ramdiskInfo) allConfig;
  };
  # pkgs.writeText "compose-info.json" (builtins.toJSON ({
  #  test_script = testScriptFile;
  #  flavour = pkgs.lib.filterAttrs (n: v: n != "extraModule") flavour;
  #} // imageInfo))
in if baseConfig then
  buildOneconfig "" { }
else
  { test_script = testScriptFile; } // imageInfo
