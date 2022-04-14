{ pkgs, ... }:
let scripts = import ./scripts/scripts.nix { inherit pkgs; };
in
{
  nodes = {
    bar = { ... }:
      {
        environment.systemPackages = [ scripts.test0-python3  ];
      };
    foo = { ... }:
      {
	      environment.systemPackages = [ scripts.test1-python3 scripts.test-bash ];
      };
  };
  testScript = ''
    bar.succeed("test0-python3")
    bar.fail("test1-python3")
    foo.succeed("test1-python3")
    foo.succeed("test-bash")
    foo.fail("test0-python3");
  '';
}
