{
  name = "nspawn";
  description = "Systemd-nspawn";
  image = { };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/common.nix ./shared/nxc.nix ];#./shared/common.nix ./shared/nxc.nix ]; #./docker/nxc-shared-dirs-docker.nix ];

   # boot.postBootCommands = ''
   #  hostname=$(cat /etc/nxc/hostname)
   #  echo "hostname name: $hostname"
   #  ${pkgs.inetutils}/bin/hostname $hostname
    # '';
   #services.sshd.enable = true;

  };
}
