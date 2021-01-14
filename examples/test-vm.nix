let
flavour = {
  name = "nixos-test";
  nixpkgs = <nixpkgs>;  
};
in
import <compose> flavour ({ pkgs, ... }: {
  nodes = {
    yop = { pkgs, lib, ... }: {

      services.sshd.enable = true;
      networking.firewall.allowedTCPPorts = [ 80 ];
      
      users.users.root.password = "nixos";
      services.openssh.permitRootLogin = lib.mkDefault "yes";
      services.mingetty.autologinUser = lib.mkDefault "root";
      

    };
  };
  testScript = ''
    yop.succeed("true")
  '';
})
