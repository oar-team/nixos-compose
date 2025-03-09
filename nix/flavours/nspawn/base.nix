/* NixOS configuration to for running a mostly normal systemd-based
   NixOS in Docker.
*/
role:
{ pkgs, lib, modulesPath, ... }: {

  imports = [ "${modulesPath}/profiles/minimal.nix" ];

  boot.isContainer = true;

  services.journald.console = "/dev/console";

  #systemd.services.systemd-logind.enable = false;
  #systemd.services.console-getty.enable = false;

  systemd.sockets.nix-daemon.enable = lib.mkDefault false;
  systemd.services.nix-daemon.enable = lib.mkDefault false;

}
