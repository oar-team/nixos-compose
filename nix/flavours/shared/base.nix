{ config, pkgs, lib, modulesPath, ... }: {
  imports = [
    "${modulesPath}/profiles/all-hardware.nix"
    "${modulesPath}/profiles/base.nix"
    ./installation-device.nix
    "${modulesPath}/installer/scan/not-detected.nix"
  ];
}
