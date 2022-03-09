{ nixpkgs, system, flavour, composition, composition_name ? "composition"
, overlays, extraConfigurations }:
let

  nixos_test = import ./nixos-test.nix;
  multiple_compositions = import ./multiple_compositions.nix;
  generate_docker_compose =
    import ./flavours/docker/generate_docker_compose.nix;

in if flavour.name == "nixos-test" then
  nixos_test { inherit nixpkgs system overlays extraConfigurations; }
  composition
else if flavour.name == "nixos-test-driver" then
  (nixos_test { inherit nixpkgs system overlays extraConfigurations; }
    composition).driver
else if flavour.name == "nixos-test-ssh" then
  (nixos_test {
    inherit nixpkgs system overlays;
    extraConfigurations = extraConfigurations ++ [ flavour.module ];
  } composition).driver
else if flavour.name == "docker" then
  generate_docker_compose {
    inherit nixpkgs system overlays extraConfigurations;
  } composition
else
  multiple_compositions {
    inherit nixpkgs system flavour extraConfigurations;
    compositions = { ${composition_name} = composition; };
  }
