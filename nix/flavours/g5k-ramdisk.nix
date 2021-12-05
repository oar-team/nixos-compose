{
  name = "g5k-ramdisk";
  description = "Flavour for Grid'5000 platform";
  image = {
    distribution = "all-in-one";
    type = "ramdisk";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/g5k-common.nix ./shared/netboot.nix ];
  };
}
