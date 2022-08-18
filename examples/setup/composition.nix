{ pkgs, setup, ... }: {
  nodes = {
    bar = { ... }:
      {
        environment.variables.A = setup.params.a;
        environment.variables.B = builtins.toString (setup.params.b + 1);
        # setup.project.selected will be set to select prolect (set to void by default)
        environment.variables.SETUP_PROJECT = setup.project.selected;
      };
  };
  testScript = ''
    bar.succeed("[[ $A == 'hello world' ]]")
    bar.succeed("[[ $B -eq 11 ]]")
  '';
}
