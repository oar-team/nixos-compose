{ pkgs, flavour, compositionName, allConfig, buildOneconfig }:
let

  rolesInfo =
    pkgs.lib.mapAttrs (n: m: m.config.system.build.initClosureInfo) allConfig;

  allRoles = builtins.attrNames rolesInfo;
  allClosureInfo =
    pkgs.lib.mapAttrsToList (n: m: "${m.closure_info}") rolesInfo;
  allStorePaths = map (x: "${x}/store-paths") allClosureInfo;

  allStoreInfo = pkgs.stdenv.mkDerivation {
    name = "all-store-info";

    buildCommand = ''
      mkdir $out
      sort ${
        builtins.concatStringsSep " " allStorePaths
      } | uniq > $out/merged-store-paths

      IFS=' ' read -r -a allClosureInfo <<< "${
        builtins.concatStringsSep " " allClosureInfo
      }"
      IFS=' ' read -r -a allRoles <<< "${
        builtins.concatStringsSep " " allRoles
      }"
      allRegistrations=""

      for index in "''${!allClosureInfo[@]}"
      do
        source="''${allClosureInfo[$index]}"/registration
        target=nix-path-registration-${compositionName}-"''${allRoles[$index]}"
        cp $source $out/$target
        echo $source $target
        allRegistrations="$allRegistrations $target"
      done

      echo $allRegistrations > $out/all-registration

    '';
  };

in {
  roles = rolesInfo;
  all_store_info = "${allStoreInfo}";
}
