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
  { lib, config, ... }: {
    imports = [
      <nixpkgs/nixos/modules/profiles/all-hardware.nix>
      <nixpkgs/nixos/modules/profiles/base.nix>
      <nixpkgs/nixos/modules/profiles/installation-device.nix>
      <nixpkgs/nixos/modules/installer/scan/not-detected.nix>
    ] ++ commonModules;
  }
