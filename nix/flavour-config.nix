flavour:
let
  commonModules = [ ./netboot.nix ./base.nix ]
    ++ (if (flavour ? extraModule) then [ flavour.extraModule ] else [ ]);
in if (flavour ? vm) && flavour.vm then
  { lib, config, modulesPath, ... }: {
    vm-shared-dir.enable = true;
    imports = [
      "${toString modulesPath}/profiles/minimal.nix"
      "${toString modulesPath}/profiles/qemu-guest.nix"
      ./base-hardware.nix
      ./installation-device.nix
    ] ++ commonModules;
  }
else
  { lib, config, modulesPath, ... }: {
    imports = [
      "${toString modulesPath}/profiles/all-hardware.nix"
      "${toString modulesPath}/profiles/base.nix"
      "${toString modulesPath}/profiles/installation-device.nix"
      "${toString modulesPath}/installer/scan/not-detected.nix"
    ] ++ commonModules;
  }
