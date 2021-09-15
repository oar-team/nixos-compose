{ config, pkgs, lib, modulesPath, ... }: {
  imports = [
    "${modulesPath}/profiles/all-hardware.nix"
    "${modulesPath}/profiles/base.nix"
    "${modulesPath}/profiles/installation-device.nix"
    "${modulesPath}/installer/scan/not-detected.nix"
  ];
}
