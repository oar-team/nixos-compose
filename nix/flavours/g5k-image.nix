{
  name = "g5k-image";
  description = "Flavour for Grid'5000 platform";
  image = {
    distribution = "all-in-one";
    type = "tarball";
  };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      ./shared/base.nix
      ./shared/stage-1-cmds.nix
      ./shared/stage-2-cmds.nix
      ./shared/common.nix
      ./shared/g5k-boot.nix
      ./shared/g5k-ssh-host-keys.nix
    ];
    # Kadeploy tests some ports' accessibility to follow deployment steps
    networking.firewall.enable = false;
  };
}
