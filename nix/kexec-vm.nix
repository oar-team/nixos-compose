{ lib, config,  modulesPath, ... }: {
  vm-shared-dir.enable = true;
  
  imports = [
      "${toString modulesPath}/profiles/minimal.nix"
      "${toString modulesPath}/profiles/qemu-guest.nix"
      ./base-hardware.nix
      ./installation-device.nix
      ./netboot.nix
      ./kexec-base.nix
      #"${toString modulesPath}/testing/test-instrumentation.nix"
    ];

}
