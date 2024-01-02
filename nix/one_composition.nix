{ nixpkgs, system, setup, nur, flavour, helpers, composition
, composition_name ? "composition", overlays, extraConfigurations }:
let
  multiple_compositions = import ./multiple_compositions.nix;
  generate_docker_compose =
    import ./flavours/docker/generate_docker_compose.nix;
  generate_nspawn_compose =
    import ./flavours/nspawn/generate_nspawn_compose.nix;
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
in if flavour.name == "docker" then
  generate_docker_compose argumentsModule composition
else if flavour.name == "nspawn" then
  generate_nspawn_compose argumentsModule composition
else
  multiple_compositions argumentsFlavourMulti
