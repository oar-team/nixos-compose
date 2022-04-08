{ config, lib, pkgs, modulesPath, ... }: {
  # move g5k-boot into g5k-image ?

  imports = [
    ./base.nix
    ./stage-1-cmds.nix
    ./common.nix
    ./nxc.nix
    ./g5k-ssh-host-keys.nix
  ];

  boot.initrd.availableKernelModules =
    [ "ahci" "ehci_pci" "megaraid_sas" "sd_mod" ];
  boot.kernelModules = [ "kvm-intel" ];

  # Kadeploy tests some ports' accessibility to follow deployment steps
  networking.firewall.enable = false;
  boot.supportedFilesystems = [ "nfs" ];
  nxc.wait-online.enable = true;

  systemd.services.nxc-script = {
    after = [ "network.target" "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig.Type = "oneshot";
    #path = [ pkgs.hostname pkgs.iproute pkgs.jq ];
    script = ''
      user=$( ${pkgs.jq}/bin/jq -r '."user" // empty' etc/nxc/deployment.json)
      mkdir -p /home/$user
      ${pkgs.util-linux}/bin/mount -t nfs nfs:/export/home/$user /home/$user'';
  };
}
