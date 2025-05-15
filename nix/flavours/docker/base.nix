/* NixOS configuration to for running a mostly normal systemd-based
   NixOS in Docker.
*/
hostname:
{ pkgs, lib, modulesPath, ... }: {
  imports = [
    "${toString modulesPath}/virtualisation/docker-image.nix"
  ];

  networking.hostName = "${hostname}";

  boot.loader.grub.enable = lib.mkForce false;
  boot.loader.systemd-boot.enable = lib.mkForce false;
  services.journald.console = "/dev/console";

  systemd.sockets.nix-daemon.enable = lib.mkDefault false;
  systemd.services.nix-daemon.enable = lib.mkDefault false;
}
