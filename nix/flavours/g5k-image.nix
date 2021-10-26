{
  name = "g5k-image";
  description = "Flavour for Grid'5000 platform";
  image = {
    distribution = "all-in-one";
    type = "tarball";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/g5k-common.nix ];

    boot.loader.grub.enable = true;
    boot.loader.grub.version = 2;
    boot.loader.grub.device = "/dev/root";

    fileSystems."/" = {
      device = "/dev/root";
      autoResize = true;
      fsType = "ext4";
    };

    swapDevices = [ ];

    nix.maxJobs = lib.mkDefault 32;
    powerManagement.cpuFreqGovernor = lib.mkDefault "powersave";
  };
}
