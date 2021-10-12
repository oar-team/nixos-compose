{
  name = "g5k-ramdisk";
  description = "Flavour for Grid'5000 platform";
  image = {
    distribution = "all-in-one";
    type = "ramdisk";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      ./shared/base.nix
      ./shared/stage-1-cmds.nix
      ./shared/stage-2-cmds.nix
      ./shared/common.nix
      ./shared/netboot.nix
      ./shared/g5k-ssh-host-keys.nix
    ];
  };
}
