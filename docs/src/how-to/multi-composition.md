# Multi-composition

Sometimes you have to composition that shares a lot in common. For example, you
want to test a tool with different integration, or run performance tests on
multiple similar tools, etc...

To do so, _NixOSCompose_ provides a simple mechanism that allows you to create
a multi-composition.

Here is a simple example of a `composition.nix` file:
```nix
{
  oar = import ./oar.nix;
  slurm = import ./slurm.nix;
}
```
Each `*.nix` file being a composition file itself. For example, the `oar.nix`
might look like:
```
{ pkgs, ... }: {
  roles =
    let
      commonConfig = import ./common_config.nix { inherit pkgs; };
    in
    {
      server = { ... }: {
        imports = [ commonConfig oarConfig ];
        services.oar.server.enable = true;
        services.oar.dbserver.enable = true;
      };

      node = { ... }: {
        imports = [ commonConfig oarConfig ];
        services.oar.node.enable = true;
      };
    };

  rolesDistribution = { node = 2; };
}
```

This compositions can be built and started with the VM flavour using the `-C` or `--composition-flavour` option:
```sh
nxc build -C oar::vm
nxc start -C oar::vm
```

