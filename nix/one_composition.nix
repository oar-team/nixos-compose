{ nixpkgs, system, setup, nur, flavour, helpers, composition
, composition_name ? "composition", overlays, extraConfigurations }:
let
  nixos_test = import ./nixos-test.nix;
  multiple_compositions = import ./multiple_compositions.nix;
  generate_docker_compose =
    import ./flavours/docker/generate_docker_compose.nix;
  commonArguments = {
    inherit nixpkgs system overlays setup nur helpers extraConfigurations;
    flavour = flavour;
  };
  argumentsModule = commonArguments // {
    extraConfigurations = extraConfigurations ++ [ flavour.module ];
  };
  argumentsFlavourMulti = commonArguments // {
    inherit flavour;
    compositions = { ${composition_name} = composition; };
  };
in if flavour.name == "nixos-test" then
  nixos_test commonArguments composition
else if flavour.name == "nixos-test-driver" then
  (nixos_test commonArguments composition).driver
else if flavour.name == "nixos-test-ssh" then
  (nixos_test argumentsModule composition).driver
else if flavour.name == "docker" then
  generate_docker_compose argumentsModule composition
else
  multiple_compositions argumentsFlavourMulti
