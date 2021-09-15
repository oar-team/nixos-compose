# This module creates netboot media containing the given NixOS
# configuration.
{ config, lib, pkgs, modulesPath, ... }:

with lib;

{
  options = {

    netboot.storeContents = mkOption {
      example = literalExample "[ pkgs.stdenv ]";
      description = ''
        This option lists additional derivations to be included in the
        Nix store in the generated netboot image.
      '';
    };

  };

  config = {
    # Don't build the GRUB menu builder script, since we don't need it
    # here and it causes a cyclic dependency.
    boot.loader.grub.enable = lib.mkDefault false;

    fileSystems."/" = {
      fsType = "tmpfs";
      options = [ "mode=0755" ];
    };

    # In stage 1, mount a tmpfs on top of /nix/store (the squashfs
    # image) to make this a live CD.
    fileSystems."/nix/.ro-store" = {
      fsType = "squashfs";
      device = "../nix-store.squashfs";
      options = [ "loop" ];
      neededForBoot = true;
    };

    fileSystems."/nix/.rw-store" = {
      fsType = "tmpfs";
      options = [ "mode=0755" ];
      neededForBoot = true;
    };

    #fileSystems."/tmp/shared" = {
    #  device = "shared";
    #  fsType = "9p";
    #  options = [ "trans=virtio" "version=9p2000.L" ];
    #};

    boot.initrd.availableKernelModules = [ "squashfs" "overlay" "igb" "ixgbe" ];
    boot.initrd.kernelModules = [ "loop" "overlay" ];

    # Closures to be copied to the Nix store, namely the init
    # script and the top-level system configuration directory.
    netboot.storeContents = [ config.system.build.toplevel ];

    # Create the squashfs image that contains the Nix store.
    system.build.squashfsStore =
      pkgs.callPackage "${toString modulesPath}/../lib/make-squashfs.nix" {
        comp = "gzip -Xcompression-level 1";
        storeContents = config.netboot.storeContents;
      };

    # Create the initrd
    system.build.netbootRamdisk = pkgs.makeInitrd {
      inherit (config.boot.initrd) compressor;
      prepend = [ "${config.system.build.initialRamdisk}/initrd" ];

      contents = [{
        object = config.system.build.squashfsStore;
        symlink = "/nix-store.squashfs";
      }];
    };

    boot.loader.timeout = 10;

    boot.initrd.network.enable = true;
    boot.initrd.extraUtilsCommands = ''
      copy_bin_and_libs ${pkgs.jq}/bin/jq
      cp -pv ${pkgs.glibc}/lib/libnss_files.so.2 $out/lib
      cp -pv ${pkgs.glibc}/lib/libresolv.so.2 $out/lib
      cp -pv ${pkgs.glibc}/lib/libnss_dns.so.2 $out/lib
    '';

    boot.postBootCommands = ''
      compositionName=""
      if [[ -f /etc/nxc-composition ]]; then
         compositionName=$(cat /etc/nxc-composition)
      fi
      echo "composition name: $compositionName"

      role=""
      if [[ -f /etc/nxc/role ]]; then
         role=$(cat /etc/nxc/role)
         ${pkgs.inetutils}/bin/hostname $role
      fi

      # Add deployment's hosts if any
      if [[ -f /etc/nxc/deployment-hosts ]]; then
         rm -f /etc/hosts
         cat /etc/static/hosts > /etc/hosts
         cat /etc/nxc/deployment-hosts >> /etc/hosts
      fi
      # Execute post boot scripts optionally provided through flavour/extraModules or composition
      for post_boot_script in $(ls -d /etc/post-boot-script* 2> /dev/null);
      do
         echo execute $post_boot_script
         $post_boot_script
      done

      # After booting, register the contents of the Nix store
      # in the Nix database in the tmpfs.
      nix_path_registration="/nix/store/nix-path-registration"
      if [[ -f "$nix_path_registration"-"$compositionName"-"$role" ]]; then
          nix_path_registration="$nix_path_registration"-"$compositionName"-"$role"
      fi
      echo "nix-store: load db $nix_path_registration"
      ${config.nix.package}/bin/nix-store --load-db < $nix_path_registration

      # nixos-rebuild also requires a "system" profile and an
      # /etc/NIXOS tag.
      touch /etc/NIXOS
      ${config.nix.package}/bin/nix-env -p /nix/var/nix/profiles/system --set /run/current-system
    '';

  };

}
