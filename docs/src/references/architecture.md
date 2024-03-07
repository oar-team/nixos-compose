# Architecture

_NixOS Compose_ works in two phases: *Build* and *Deploy*

> TODO: Overview diagram

## Build Phase

The build phase triggered by `nxc build` takes the Composition and the Flavor and create a NixOS configuration.

To do so, It uses Nix and the provided composition to create one configuration per Role. All the configurations are put in the Nix store and referenced using a JSON file. A symlink to this file is kept in the `build` directory with the name formatted as `[composition]::[flavor]`. 

## Deploy Phase

Once the build is done, you can run `nxc start`.  This phase does not use Nix directly, but it uses the provided build file, and an optional `role-distribution` to contextualize the deployment. With these elements it creates a JSON file within the  `deploy` directory containing all the details about the deployment.

Then, the deployment is finally applied with the driver that will deploy the environment, using the appropriate methods depending on the flavor.
