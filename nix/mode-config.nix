mode:
if (mode ? vm) && mode.vm then
  { lib, config, modulesPath, ... }: {
    vm-shared-dir.enable = true;
    imports = [
      "${toString modulesPath}/profiles/minimal.nix"
      "${toString modulesPath}/profiles/qemu-guest.nix"
      ./base-hardware.nix
      ./installation-device.nix
      ./netboot.nix
      ./base.nix
      #"${toString modulesPath}/testing/test-instrumentation.nix"
    ];
  }
else
  { lib, config, ... }: {
    imports = [
      <nixpkgs/nixos/modules/profiles/all-hardware.nix>
      <nixpkgs/nixos/modules/profiles/base.nix>
      <nixpkgs/nixos/modules/profiles/installation-device.nix>
      <nixpkgs/nixos/modules/installer/scan/not-detected.nix>
      ./netboot.nix
      ./base.nix
      #"${toString modulesPath}/testing/test-instrumentation.nix"
    ];
  }

