{ nixpkgs, system, compositions, flavour, extraConfigurations }:
let
  pkgs = (import nixpkgs) { inherit system; };
  modulesPath = "${toString nixpkgs}/nixos";
  flavours = import ./flavours.nix;
  generate = import ./generate_one_composition_info.nix;

  allCompositionsInfo = pkgs.lib.mapAttrs (compositionName: composition:
    generate { inherit pkgs modulesPath system extraConfigurations flavour; } {
      inherit compositionName composition;
    }) compositions;

  allMergedStorePaths =
    pkgs.lib.mapAttrsToList (n: m: "${m.all_store_info}/merged-store-paths")
    allCompositionsInfo;
  allCompositionsInfoPaths =
    pkgs.lib.mapAttrsToList (n: m: "${m.all_store_info}") allCompositionsInfo;

  allCompositionsSquashfsStore = pkgs.stdenv.mkDerivation {
    name = "all-compositions-squashfs.img";

    nativeBuildInputs = [ pkgs.squashfsTools ];

    buildCommand = ''
      allMergedStorePaths=$(sort ${
        builtins.concatStringsSep " " allMergedStorePaths
      } | uniq)

      IFS=' ' read -r -a allCompositionsInfoPaths <<< "${
        builtins.concatStringsSep " " allCompositionsInfoPaths
      }"

      allRegistrations=""
      for compositionsInfoPath in "''${allCompositionsInfoPaths[@]}"
      do
        for registrationFile in "$compositionsInfoPath"/nix-path-registration*
        do
          cp $registrationFile .
          echo "copy $registrationFile"
          allRegistrations="$allRegistrations $registrationFile"
        done
      done

      # Generate the squashfs image.
      mksquashfs  $allRegistrations $allMergedStorePaths $out \
        -keep-as-directory -all-root -b 1048576 -comp gzip -Xcompression-level 1;
    '';
  };

  baseConfig = generate {
    inherit pkgs modulesPath system extraConfigurations flavour;
    baseConfig = true;
  } { };

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

  allRamdisk = pkgs.makeInitrd {
    inherit (baseConfig.config.boot.initrd) compressor;
    prepend = [ "${baseConfig.config.system.build.initialRamdisk}/initrd" ];

    contents = [{
      object = allCompositionsSquashfsStore;
      symlink = "/nix-store.squashfs";
    }];
  };

in pkgs.writeText "compose-info.json" (builtins.toJSON ({
  flavour = flavour;
  compositions_info = allCompositionsInfo;
  compositions_squashfs_store = allCompositionsSquashfsStore;
  all = {
    kernel = "${baseImage}/kernel";
    qemu_script = "${baseConfig.config.system.build.qemu_script}";
    initrd = "${allRamdisk}/initrd";
  };
}))
