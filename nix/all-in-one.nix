{ pkgs, flavour, allConfig, buildOneconfig }:
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

  allSquashfsStore = pkgs.stdenv.mkDerivation {
    name = "all-squashfs.img";

    nativeBuildInputs = [ pkgs.squashfsTools ];

    buildCommand = ''
      sort ${
        builtins.concatStringsSep " " allStorePaths
      } | uniq > merged-store-paths

      IFS=', ' read -r -a allClosureInfo <<< "${
        builtins.concatStringsSep " " allClosureInfo
      }"
      IFS=', ' read -r -a allRoles <<< "${
        builtins.concatStringsSep " " allRoles
      }"
      allRegistrations=""

      for index in "''${!allClosureInfo[@]}"
      do
        source="''${allClosureInfo[$index]}"/registration
        target=nix-path-registration-"''${allRoles[$index]}"
        cp $source $target
        echo $source $target
        allRegistrations="$allRegistrations $target"
      done

      # Generate the squashfs image.
      mksquashfs $allRegistrations $(cat merged-store-paths) $out \
        -keep-as-directory -all-root -b 1048576 -comp gzip -Xcompression-level 1;
    '';
  };

  allRamdisk = pkgs.makeInitrd {
    inherit (baseConfig.config.boot.initrd) compressor;
    prepend = [ "${baseConfig.config.system.build.initialRamdisk}/initrd" ];

    contents = [{
      object = allSquashfsStore;
      symlink = "/nix-store.squashfs";
    }];
  };

in {
  nodes = machinesInfo;
  all = {
    squashfs_img = "${allSquashfsStore}";
    initrd = "${allRamdisk}/initrd";
    kernel = "${baseImage}/kernel";
    qemu_script = "${baseConfig.config.system.build.qemu_script}";
  };
}
