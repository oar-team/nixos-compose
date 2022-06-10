{ pkgs, ... }: {
  nodes = {
    bar = { pkgs, lib, ... }:
      {

      };
  };
  testScript = ''
    bar.succeed("true")
  '';
}
