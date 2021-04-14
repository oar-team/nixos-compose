{ pkgs, ... }: {
  nodes = {
    foo = { pkgs, lib, ... }: {

      services.sshd.enable = true;

      users.users.root.password = "nixos";
      services.openssh.permitRootLogin = lib.mkDefault "yes";
      services.getty.autologinUser = lib.mkDefault "root";

    };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
