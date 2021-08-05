flavour:
let
  commonModules = [ ./netboot.nix ./base.nix ]
    ++ (if (flavour ? extraModule) then [ flavour.extraModule ] else [ ]);
in if (flavour ? vm) && flavour.vm then
  { lib, config, modulesPath, ... }: {
    vm-shared-dir.enable = true;
    imports = [
      "${modulesPath}/profiles/minimal.nix"
      "${modulesPath}/profiles/qemu-guest.nix"
      ./base-hardware.nix
      ./installation-device.nix
    ] ++ commonModules;
  }
else
  { lib, config, modulesPath, ... }: {
    imports = [
      "${modulesPath}/profiles/all-hardware.nix"
      "${modulesPath}/profiles/base.nix"
      "${modulesPath}/profiles/installation-device.nix"
      "${modulesPath}/installer/scan/not-detected.nix"
    ] ++ commonModules;
  }
