{
  name = "vm-ramdisk";
  description = "Plain vm ramdisk (all-in-memory), need lot of ram !";
  vm = true;
  image = {
    type = "ramdisk";
    distribution = "all-in-one";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      ./shared/netboot.nix
      ./shared/base-vm.nix
      ./shared/stage-1-cmds.nix
      ./shared/common.nix
      ./shared/nxc.nix
    ];
    nxc.qemu-script.enable = true;
  };
}
