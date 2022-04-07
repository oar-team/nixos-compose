{ config, pkgs, lib, modulesPath, ... }:

with lib; {

  options = {
    nxc = {
      qemu-script = {
        enable = mkEnableOption "Build qemu and qemu_script (take space)";
      };
      wait-online = {
        enable = mkEnableOption "Wait to network is operational";
      };
    };
  };

  config = mkIf config.nxc.wait-online.enable {
    systemd.services.nxc-network-wait-online = {
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" "network-online.target" ];
      serviceConfig.Type = "oneshot";
      script = ''
        # wait network is ready
        while ! ${pkgs.iproute}/bin/ip route get 1.0.0.0 ; do
        sleep .2
        done
      '';
    };
  };
}
