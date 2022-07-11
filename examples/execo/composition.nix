{ pkgs, ... }: {
  nodes = {
    foo = { pkgs, ... }:
      {
        # add needed package
        environment.systemPackages = with pkgs; [ hello ];
      };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
