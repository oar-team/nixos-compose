{ nixpkgs, system, flavour, overlays ? [ ], setup ? { }, nur ? { }, extraConfigurations ? [ ]
,helpers, ... }:
composition:

let
  pkgs = (import nixpkgs) { inherit system overlays; };
  lib = pkgs.lib;
  modulesPath = "${toString nixpkgs}/nixos";

  roleConfigWithoutVirtualisation = configRole:
    args@{ pkgs, ... }:
    removeAttrs
      (if lib.isFunction configRole then configRole args else configRole)
      [ "virtualisation" ];

  buildOneconfig = roleName: roleConfig:
    pkgs.nixos {
      imports = [
        (import ./base.nix roleName)
        (roleConfigWithoutVirtualisation roleConfig)
        { _module.args.nodes = nodes; }
        { system.stateVersion = lib.mkDefault lib.trivial.release; }
      ] ++ extraConfigurations;
    };

  # FIXME: extract the common part in future refactor
  # see `nix/generate_one_composition_info.nix` for the fixed-point rationale
  nodes = lib.mapAttrs (_: c: c.config // { config = c.config; }) allConfig;

  compositionSet =
    if lib.isFunction composition then
      composition { inherit pkgs lib system modulesPath helpers flavour setup nur nodes; }
    else
      composition;

  roles = if compositionSet ? roles then compositionSet.roles else compositionSet.nodes;

  allConfig = lib.mapAttrs buildOneconfig roles;

  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${if compositionSet ? testScript then compositionSet.testScript else ""}";
  };

  # only rolesDistribution, could be extended
  optionalCompositionAttr = if compositionSet ? rolesDistribution then
    { roles_distribution = compositionSet.rolesDistribution; }
                            else {};

  # name and tag of the base container image
  name = "nxc-docker-base-image";
  tag = "latest";
  image = import ./generate_image.nix { inherit pkgs name tag; };
  dockerComposeConfig = {
    x-nxc = { inherit image; };
    #volumes = { nxc-shared = { external = false; }; };
    volumes = { nxc-shared = null; };
  };
  baseEnv = pkgs.buildEnv {
    name = "container-system-env";
    paths = [ pkgs.bashInteractive pkgs.coreutils ];
  };

  extraVolumes =
    if compositionSet ? extraVolumes then compositionSet.extraVolumes else [ ];

  dockerPorts =
    if compositionSet ? dockerPorts then compositionSet.dockerPorts else { };

  dockerComposeConfig.services = lib.mapAttrs (roleName: _:
    let
      builtConfig = allConfig.${roleName};
    in {
      privileged = true;
      cgroup = "host";
      cap_add = [ "SYS_ADMIN" "SYS_NICE" ];
      command = [ "${builtConfig.toplevel}/init" ];
      environment = {
        NIX_REMOTE = "";
        PATH = "/bin:/usr/bin:/run/current-system/sw/bin";
        container = "docker";
      };
      hostname = roleName;
      image = "${name}:${tag}";
      stop_signal = "SIGINT";
      tmpfs = [ "/run" "/run/wrappers:exec,suid" "/tmp:exec,mode=777" ];
      tty = true;
      volumes = [
        "/sys/fs/cgroup:/sys/fs/cgroup:rw"
        "/nix/store:/nix/store:ro"
        "${baseEnv}:/run/system:ro"
        "/tmp/shared:/tmp/shared:rw"
        "nxc-shared:/var/nxc/shared"
      ] ++ extraVolumes;
      ports =
        if dockerPorts ? "${roleName}" then dockerPorts."${roleName}" else [ ];
    }) roles;

  dockerComposeConfigJSON = pkgs.writeTextFile {
    name = "docker-compose";
    text = builtins.toJSON dockerComposeConfig;
  };

in pkgs.writeTextFile {
  name = "compose-info.json";
  text = builtins.toJSON ({
    inherit image;
    roles = builtins.attrNames roles;
    docker-compose-file = dockerComposeConfigJSON;
    test_script = testScriptFile;
    flavour = flavour.name;
  } // optionalCompositionAttr );
}
