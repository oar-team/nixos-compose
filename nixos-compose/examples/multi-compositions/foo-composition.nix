{ pkgs, ... }: {
  nodes = {
    foo = { pkgs, lib, ... }:
      {

      };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
