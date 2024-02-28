# Import Flakes

If you want to use packages, modules, or libraries form another Nix Flake, you can make it available in your composition using an overlay.

In order to add this overlay, you have to edit the `flake.nix` file and add your flake as input. For example:
```nix
  inputs = {
    # ...
    myFlake.url = "github:myTeam/myFlake";
  };
```

Here is how you can add a extra package using an overlay or add a NixOS module using the `extraConfigurations` parameter:
```nix
  outputs = { self, nixpkgs, nxc, myFlake }:
    let
      system = "x86_64-linux";
    in
    {
      packages.${system} = nxc.lib.compose {
        inherit nixpkgs system;

        # Use this to make a NixOS module available
        extraConfigurations = [ myFlake.nixosModules.myModule ];

        # Use this to make a Nix package available
        overlays = [
           (self: super: {
             myTool = myFlake.packages.${system}.myTool;
           })
        ];
        setup = ./setup.toml;
        compositions = ./composition.nix;
      };
    };
    # ...
}
```
> [!NOTE]
> For more details on overlays, checkout the [Nixpkgs documentation on Overlays](https://nixos.org/manual/nixpkgs/stable/#sec-overlays-definition)

You can now use your package or your module in your composition just like the
ones present in nixpkgs, for example:
```nix
{ pkgs }:
{
  roles = {
    node1 = {
      services.myService.enabled = true;
    }
    node2 = {
      environment.systemPackages = with pkgs; [ pkgs.myTool ];
    }
  };
}
```

