{ pkgs, setup, ... }: {
  nodes = {
    bar = { ... }:
      {
        environment.variables.A = setup.params.a;
        environment.variables.B = builtins.toString (setup.params.b + 1);
      };
  };
  testScript = ''
    bar.succeed("[[ $A == 'hello world' ]]")
    bar.succeed("[[ $B -eq 11 ]]")
  '';
}
