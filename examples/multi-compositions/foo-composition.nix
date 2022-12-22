{ pkgs, ... }: {
  roles = {
    foo = { pkgs, lib, ... }:
      {

      };
  };
  testScript = ''
    foo.succeed("true")
  '';
}
