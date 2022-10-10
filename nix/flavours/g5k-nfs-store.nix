{
  name = "g5k-nfs-store";
  description = "Flavour for Grid'5000 platform";
  image = {
    distribution = "all-in-one";
    type = "remote-store";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/g5k-common.nix ];

    boot.loader.grub.enable = lib.mkDefault false;

    #boot.initrd.postDeviceCommands = ''
    #allowShell=1
    #nfs_store="nfs.domaine.fr:/path/to/store"
    #'';

    fileSystems."/" = {
      fsType = "tmpfs";
      options = [ "mode=0755" ];
    };

    boot.initrd.network.enable = true;
    boot.initrd.kernelModules =
      [ "squashfs" "loop" "overlay" "nfsv3" "igb" "ixgbe" ];

    # Required for nfs mount to work in the early of stage-2
    boot.initrd.network.flushBeforeStage2 = false;

    systemd.services.nxc-bindfs = {
      before = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig.Restart= "always";
      script = ''
        uid=$(stat -c '%u' /nix/.server-ro-store)
        gid=$(stat -c '%g' /nix/.server-ro-store)
        echo "Launch bindfs userid/groudid: $uid/$gid"
        ${pkgs.bindfs}/bin/bindfs -f --map=$uid/0:@$gid/@0 /nix/store /nix/store
      '';
    };
  };
}
