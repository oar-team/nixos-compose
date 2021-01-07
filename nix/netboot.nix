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
    boot.loader.grub.enable = false;

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

    boot.initrd.availableKernelModules = [ "squashfs" "overlay" ];
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

      #copy_bin_and_libs ${pkgs.strace}/bin/strace
      #cp -pv ${pkgs.glibc}/lib/libgcc_s.so.1 $out/lib

      cp -pv ${pkgs.glibc}/lib/libnss_files.so.2 $out/lib
      cp -pv ${pkgs.glibc}/lib/libresolv.so.2 $out/lib
      cp -pv ${pkgs.glibc}/lib/libnss_dns.so.2 $out/lib
    '';

    boot.postBootCommands = ''
      role=""
      if [[ -f /etc/role ]]; then
         role=$(cat /etc/role)
         ${pkgs.inetutils}/bin/hostname $role
      fi

      # Add deployment's hosts if any
      if [[ -f /etc/deployment-hosts ]]; then
         rm -f /etc/hosts
         cat /etc/static/hosts > /etc/hosts
         cat /etc/deployment-hosts >> /etc/hosts
      fi

      # After booting, register the contents of the Nix store
      # in the Nix database in the tmpfs.
      nix_path_registration="/nix/store/nix-path-registration"
      if [[ -f $nix_path_registration$role ]]; then
          nix_path_registration=$nix_path_registration$role
      fi
      ${config.nix.package}/bin/nix-store --load-db < $nix_path_registration

      # nixos-rebuild also requires a "system" profile and an
      # /etc/NIXOS tag.
      touch /etc/NIXOS
      ${config.nix.package}/bin/nix-env -p /nix/var/nix/profiles/system --set /run/current-system
    '';

  };

}
