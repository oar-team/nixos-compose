# Provide a basic configuration for installation devices like CDs.
{ config, pkgs, lib, modulesPath, ... }:

with lib;

{
  imports =
    [ # Enable devices which are usually scanned, because we don't know the
      # target system.
      "${toString modulesPath}/installer/scan/detected.nix"
      "${toString modulesPath}/installer/scan/not-detected.nix"

      # Allow "nixos-rebuild" to work properly by providing
      # /etc/nixos/configuration.nix.
      #"${toString modulesPath}/profiles/clone-config.nix"

      # Include a copy of Nixpkgs so that nixos-install works out of
      # the box.
      #"${toString modulesPath}/installer/cd-dvd/channel.nix"
    ];

  config = {

    # Enable in installer, even if the minimal profile disables it.
    #documentation.enable = mkForce true;

    # Show the manual.
    #documentation.nixos.enable = mkForce true;

    # To speed up installation a little bit, include the complete
    # stdenv in the Nix store on the CD.
    system.extraDependencies = with pkgs; [
      #stdenv
      stdenvNoCC # for runCommand
      busybox
      jq # for closureInfo
    ];

    # Show all debug messages from the kernel but don't log refused packets
    # because we have the firewall enabled. This makes installs from the
    # console less cumbersome if the machine has a public IP.
    networking.firewall.logRefusedConnections = mkDefault false;
  };
}
