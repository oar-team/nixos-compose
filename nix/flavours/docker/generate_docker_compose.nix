{ nixpkgs, system, flavour, overlays ? [ ], setup ? { }, nur ? { }, extraConfigurations ? [ ]
,helpers, ... }:
composition:

let
  pkgs = (import nixpkgs) { inherit system overlays; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";
  compositionSet = composition { inherit pkgs lib system modulesPath helpers flavour setup nur; };

  roles = if compositionSet ? roles then compositionSet.roles else compositionSet.nodes;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${if compositionSet ? testScript then compositionSet.testScript else ""}";
  };

  # name and tag of the base container image
  name = "nxc-docker-base-image";
  tag = "latest";
  image = import ./generate_image.nix { inherit pkgs name tag; };
  dockerComposeConfig = {
    version = "3.4";
    x-nxc = { inherit image; };
  };
  baseEnv = pkgs.buildEnv {
    name = "container-system-env";
    paths = [ pkgs.bashInteractive pkgs.coreutils ];
  };

  extraVolumes =
    if compositionSet ? extraVolumes then compositionSet.extraVolumes else [ ];

  dockerPorts =
    if compositionSet ? dockerPorts then compositionSet.dockerPorts else { };

  dockerComposeConfig.services = builtins.mapAttrs (nodeName: nodeConfig:
    let
      nodeConfigWithoutVirutalisation = configNode:
        args@{ pkgs, ... }:
        builtins.removeAttrs (configNode args) [ "virtualisation" ];
      config = {
        system.stateVersion = lib.mkDefault lib.trivial.release;
        imports = [ (import ./systemd.nix nodeName)  (nodeConfigWithoutVirutalisation nodeConfig) ]
          ++ extraConfigurations;
      };
      builtConfig = pkgs.nixos config;
    in {
      cap_add = [ "SYS_ADMIN" ];
      command = [ "${builtConfig.toplevel}/init" ];
      environment = {
        NIX_REMOTE = "";
        PATH = "/bin:/usr/bin:/run/current-system/sw/bin";
        container = "docker";
      };
      hostname = nodeName;
      image = "${name}:${tag}";
      stop_signal = "SIGINT";
      #privileged = true;
      tmpfs = [ "/run" "/run/wrappers:exec,suid" "/tmp:exec,mode=777" ];
      tty = true;
      volumes = [
        "/sys/fs/cgroup:/sys/fs/cgroup:rw" # UGLY need with systemd > 247 and docker 20.10 and systemd.unifiedCgroupHierarchy=0 (use cgroup v1)
        "/nix/store:/nix/store:ro"
        "${baseEnv}:/run/system:ro"
        "/tmp/shared:/tmp/shared:rw"
      ] ++ extraVolumes;
      ports =
        if dockerPorts ? "${nodeName}" then dockerPorts."${nodeName}" else [ ];
    }) roles;

  dockerComposeConfigJSON = pkgs.writeTextFile {
    name = "docker-compose";
    text = builtins.toJSON dockerComposeConfig;
  };

in pkgs.writeTextFile {
  name = "compose-info.json";
  text = (builtins.toJSON {
    inherit image;
    roles = builtins.attrNames roles;
    docker-compose-file = dockerComposeConfigJSON;
    test_script = testScriptFile;
    flavour = flavour.name;
  });
}
