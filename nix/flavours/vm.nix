{
  name = "vm";
  description = "vm ";
  vm = true;
  image.distribution = "all-in-one";

  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      ./shared/base-vm.nix
      ./shared/vm-stage-1-cmds.nix
      ./shared/common.nix
      ./shared/nxc.nix
    ];
    nxc.qemu-script.enable = true;

    boot.loader.grub.enable = false;

    fileSystems."/" = {
      fsType = "tmpfs";
      options = [ "mode=0755" ];
    };

    # Little latency optimisation
    boot.initrd.network.flushBeforeStage2 = false;

    boot.initrd.availableKernelModules = [ "overlay" "igb" "ixgbe" ];
    boot.initrd.kernelModules = [ "squashfs" "overlay" ];

    # TOTEST ON G5K !!!
    # Workaround for sudo issue w/ nfs-store owned by other than root
    # sudo: error in /etc/sudo.conf, line 0 while loading plugin "sudoers_policy"
    # sudo: /nix/store/phzwlf32mgx2a8xvwz6yxql679rl3jwf-sudo-1.9.10/libexec/sudo/sudoers.so must be owned by uid 0
    # sudo: fatal error, unable to load plugins
    # TODO: add test if store is owned by root or other user
    systemd.services.nxc-bindfs-sudo = {
      before = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig.Restart= "always";
      script = ''
        echo "Launch bindfs for sudo (its files required to be owned by root)"
        ${pkgs.bindfs}/bin/bindfs -f --force-user=root --force-group=root ${pkgs.sudo} ${pkgs.sudo}
    #   '';
    };

  };
}
