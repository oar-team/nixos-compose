{ pkgs, ... }: {
  nodes = {
    foo = { pkgs, lib, ... }: {

      services.sshd.enable = true;
      networking.firewall.allowedTCPPorts = [ 80 ];

      users.users.root.password = "nixos";
      services.openssh.permitRootLogin = lib.mkDefault "yes";
      services.mingetty.autologinUser = lib.mkDefault "root";

    };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
