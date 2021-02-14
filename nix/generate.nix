{ nixpkgs, flavour, ... }:
composition:

let
  pkgs = (import nixpkgs) { };

  compositionSet = composition { pkgs = pkgs; };
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

  commonConfig = import ./common-config.nix flavour;
  flavourConfig = import ./flavour-config.nix flavour;

  buildOneconfig = machine: configuration:
    import "${toString nixpkgs}/nixos/lib/eval-config.nix" {
      #inherit system;
      inherit pkgs;
      modules = [ configuration commonConfig vmSharedDirMod flavourConfig ];
    };

in let
  allConfig = pkgs.lib.mapAttrs buildOneconfig nodes;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${testScript}";
  };

  imageInfo = if flavour.image ? distribution && flavour.image.distribution
  == "all-in-one" then
    import ./all-in-one.nix { inherit pkgs flavour allConfig buildOneconfig; }
  else {
    nodes =
      pkgs.lib.mapAttrs (n: m: m.config.system.build.ramdiskInfo) allConfig;
  };
in {
  composeInfo = pkgs.writeText "compose-info.json" (builtins.toJSON ({
    test_script = testScriptFile;
    flavour = pkgs.lib.filterAttrs (n: v: n != "extraModule") flavour;
  } // imageInfo));
}
