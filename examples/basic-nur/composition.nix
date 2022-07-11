{ pkgs, ... }: {
  nodes = {
    foo = { pkgs, ... }:
      {
        # add needed package
        # environment.systemPackages = with pkgs; [ socat ];
      };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
