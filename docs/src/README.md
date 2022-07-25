_NixOSCompose_ generates and deploys reproducible distributed environnements, with a focus on the software stack.

<!-- build and deploy config and software stack on different target platform with a focus on reproducibility -->
<!-- parler environment + configuration (service, ssh key, ) ; deployable on different target platforms -->
# Introduction

## Presentation

_NixOSCompose_ is a tool designed for experiments in distributed systems. It generates reproducible distributed environments. Those can then be deploy either in virtualized or physical platform, respectively for local and distributed deployments. It inserts itself in the development cylce of the environments and uses to the notion of transposition to make it faster and easier. The intended workflow is to have fast iteration cycle on a local virtualized distributed system and once the configuration is complete it can be used for physical deployment.

```admonish abstract title="Transposition"
Enables users to have a single definition of their environment and to deploy it to different platforms. instead of maintaining multiple configuration for each targeted platforms we are using only one declarative description (called `composition`).
```

The command line tool provides a similar interaction between the different targeted platforms that we call _flavours_

## [NixOS](https://www.nixos.org)

As seen in the name of the project, NixOS plays an important role here. We exploit the declarative approach for system configuration provided by the NixOS Linux distribution. We also rely on the reproducibility provided by the Nix package manager which helps in the sharing and rerun of experiments.

# Current support

Right now _NixOSCompose_ is still in early stage of development, it supports the following list of flavours.
## Supported _Flavours_

A _flavour_ is a target platform, the same composition/environments is produced in different flavours.
Currently _NixCompose_ support the following flavours:
### Local

| flavour  |  local |  distributed |  test |  comments |
|---|---|---|---|---|
| docker  | x  |   |   |  Produces a docker compose |
|   |   |   |   |   |
|   |   |   |   |   |

- docker

Produces a docker compose 

- vm-ramdisk

sets-up VMs

``` admonish
a quel point on supporte les flavours ci-dessous ?
```
- nixos-test

uses default nixos-test

- nixos-test-driver

nixos-test wit interactivity

- nixos-test-ssh

nixos test with ssh access

### Physical

- g5k-image
- g5k-ramdisk