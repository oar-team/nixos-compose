{ config, lib, pkgs, modulesPath, ... }:

{

  # Set and select root system by label (nixos)
  boot.initrd.extraUtilsCommands = ''
    copy_bin_and_libs ${pkgs.e2fsprogs}/bin/e2label
  '';

  # set -- $(IFS==; echo $o)
  #          if [ $2 = "LABEL" ]; then
  #              root="/dev/disk/by-label/$3"
  #          elif [ $2 = "UUID" ]; then
  #              root="/dev/disk/by-uuid/$3"
  #          else
  #              root=$2
  #          fi

  boot.initrd.postDeviceCommands = ''

    allowShell=1
    #echo Breakpoint reached && fail
    for o in $(cat /proc/cmdline); do
    case $o in
            root=*)

                disk_uuid=/dev/disk/by-uuid/$(echo $o | cut -c11-)
                waitDevice $disk_uuid
                e2label $disk_uuid nixos
                ;;
        esac
    done
    fail
  '';

  # Use the GRUB 2 boot loader.
  boot.loader.grub.enable = true;
  boot.loader.grub.version = 2;
  boot.loader.grub.device = "/dev/sda3";

  boot.initrd.availableKernelModules =
    [ "ahci" "ehci_pci" "megaraid_sas" "sd_mod" ];
  boot.kernelModules = [ "kvm-intel" ];

  fileSystems."/" = {
    device = "/dev/disk/by-label/nixos";
    autoResize = true;
    fsType = "ext4";
  };

  swapDevices = [ ];

  nix.maxJobs = lib.mkDefault 32;
  powerManagement.cpuFreqGovernor = lib.mkDefault "powersave";

  # system.build.g5k-image-info = pkgs.writeText "g5k-image-info.json"
  #   (builtins.toJSON {
  #     kernel = config.boot.kernelPackages.kernel + "/"
  #       + config.system.boot.loader.kernelFile;
  #     initrd = config.system.build.initialRamdisk + "/"
  #       + config.system.boot.loader.initrdFile;
  #     init = "${
  #         builtins.unsafeDiscardStringContext config.system.build.toplevel
  #       }/init";
  #     image = "${config.system.build.g5k-image}/tarball/${image_name}.tar.xz";
  #     kaenv = config.system.build.kadeploy_env_description;
  #   });

  # system.build.g5k-image-all = pkgs.stdenv.mkDerivation {
  #   name = "g5k-image-all";
  #   dontUnpack = true;
  #   doCheck = false;

  #   installPhase = ''
  #     mkdir $out
  #     ln -s ${config.system.build.g5k-image-info} $out/g5k-image-info.json
  #     ln -s ${config.system.build.kadeploy_env_description} $out/image_name.yaml
  #     ln -s ${config.system.build.g5k-image}/tarball/all-compositions-system-tarball.tgz $out/g5k-image.tar.xz
  #   '';
  # };

  boot.postBootCommands = ''
    # After booting, register the contents of the Nix store on the
    # CD in the Nix database in the tmpfs.
    if [ -f /nix-path-registration ]; then
    ${config.nix.package.out}/bin/nix-store --load-db < /nix-path-registration &&
    rm /nix-path-registration
    fi

    # nixos-rebuild also requires a "system" profile and an
    # /etc/NIXOS tag.
    touch /etc/NIXOS
    ${config.nix.package.out}/bin/nix-env -p /nix/var/nix/profiles/system --set /run/current-system
  '';

  system.build.kadeploy_env_description = pkgs.writeTextFile {
    name = "{image_name}.yaml";
    text = ''
      name: {image_name}
      version: 1
      description: NixOS
      author: {author}
      visibility: shared
      destructive: false
      os: linux
      image:
        file: {file_image_baseurl}/{image_name}.tar.xz
        kind: tar
        compression: xz
      postinstalls:
      - archive: {postinstall}
        compression: gzip
        script:  {postinstall_args}
      boot:
        kernel: /boot/bzImage
        initrd: /boot/initrd
        kernel_params: init=boot/init console=tty0 console=ttyS0,115200
      filesystem: ext4
      partition_type: 131
      multipart: false
    '';
  };

}
