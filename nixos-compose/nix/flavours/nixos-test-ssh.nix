{
  name = "nixos-test-ssh";
  description =
    "Nixos Test Driver from provided Nixpkgs but managed differently (forwared ssh ports)";
  module = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      ./shared/stage-1-cmds.nix
      ./shared/nxc.nix
      ./shared/common.nix
    ];
    networking.firewall.enable = false;
    services.sshd.enable = true;
  };
}
