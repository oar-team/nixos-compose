{
  name = "docker";
  description = "Docker-Compose based";
  image = { };
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [ ./shared/nxc.nix ];
  };
}
