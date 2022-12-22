{ pkgs, ... }: {
  roles = {
    bar = { pkgs, lib, ... }:
      {

      };
  };
  testScript = ''
    bar.succeed("true")
  '';
}
