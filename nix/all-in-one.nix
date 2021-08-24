{ pkgs, flavour, compositionName, allConfig, buildOneconfig }:
let

  baseConfig = buildOneconfig "" { };
  baseImage =
    pkgs.runCommand "image" { buildInputs = [ pkgs.nukeReferences ]; } ''
      mkdir $out
      cp ${baseConfig.config.system.build.kernel}/bzImage $out/kernel
      echo "init=${
        builtins.unsafeDiscardStringContext
        baseConfig.config.system.build.toplevel
      }/init ${toString baseConfig.config.boot.kernelParams}" > $out/cmdline
      nuke-refs $out/kernel
    '';

  machinesInfo =
    pkgs.lib.mapAttrs (n: m: m.config.system.build.initClosureInfo) allConfig;

  allRoles = builtins.attrNames machinesInfo;
  allClosureInfo =
    pkgs.lib.mapAttrsToList (n: m: "${m.closure_info}") machinesInfo;
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
  nodes = machinesInfo;

  all_store_info = "${allStoreInfo}";
  #  #initrd = "${allRamdisk}/initrd";
  #  #TODO move kerne
  #  kernel = "${baseImage}/kernel";
  #  qemu_script = "${baseConfig.config.system.build.qemu_script}";
  #};
}
