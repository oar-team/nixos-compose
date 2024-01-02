{
  name = "nspawn";
  description = "Systems-nspawn";
  image = { };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/common.nix ./shared/nxc.nix ]; #./docker/nxc-shared-dirs-docker.nix ];
  };
}
