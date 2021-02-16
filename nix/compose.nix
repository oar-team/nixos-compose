flavourOptionsRaw: composition:

let
  flavours = import ./flavours-meta.nix;

  flavourOptions = if builtins.typeOf flavourOptionsRaw == "path" then
  # -I flavour=./flavours/kexec-g5k.nix (import set))
    import flavourOptionsRaw
  else
    flavourOptionsRaw;

  nixpkgs =
    if flavourOptions ? nixpkgs then flavourOptions.nixpkgs else <nixpkgs>;

  flavour = if flavours ? "${flavourOptions.name}" then
    flavours."${flavourOptions.name}" // flavourOptions
  else
    flavourOptions;

  f = if (flavour ? name && flavour.name == "nixos-test") then
    import ./nixos-test.nix
  else
    import ./generate.nix;
in f { inherit nixpkgs flavour; } composition
