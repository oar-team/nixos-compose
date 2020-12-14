{ pkgs, config, ... }:
let
  sshKeys = import <nixpkgs/nixos/tests/ssh-keys.nix> pkgs;
  snakeOilPrivateKey = sshKeys.snakeOilPrivateKey.text;
  snakeOilPrivateKeyFile = pkgs.writeText "private-key" snakeOilPrivateKey;
  snakeOilPublicKey = sshKeys.snakeOilPublicKey;
in {
  system.build = rec {
    image =
      pkgs.runCommand "image" { buildInputs = [ pkgs.nukeReferences ]; } ''
        mkdir $out
        cp ${config.system.build.kernel}/bzImage $out/kernel
        cp ${config.system.build.netbootRamdisk}/initrd $out/initrd
        echo "init=${
          builtins.unsafeDiscardStringContext config.system.build.toplevel
        }/init ${toString config.boot.kernelParams}" > $out/cmdline
        nuke-refs $out/kernel
      '';
    kexec_script = pkgs.writeTextFile {
      executable = true;
      name = "kexec-nixos";
      text = ''
        #!${pkgs.stdenv.shell}
        export PATH=${pkgs.kexectools}/bin:${pkgs.cpio}/bin:$PATH
        set -x
        set -e
        cd $(mktemp -d)
        pwd
        mkdir initrd
        pushd initrd
        if [ -e /ssh_pubkey ]; then
          cat /ssh_pubkey >> authorized_keys
        fi
        find -type f | cpio -o -H newc | gzip -9 > ../extra.gz
        popd
        cat ${image}/initrd extra.gz > final.gz

        kexec -l ${image}/kernel --initrd=final.gz --append="init=${
          builtins.unsafeDiscardStringContext config.system.build.toplevel
        }/init ${toString config.boot.kernelParams}"
        sync
        echo "executing kernel, filesystems will be improperly umounted"
        kexec -e
      '';
    };
  };
  boot.initrd.postMountCommands = ''
    for o in $(cat /proc/cmdline); do
        case $o in
            server=*)
                set -- $(IFS==; echo $o)
                echo "$2 server" > /etc/hosts
                ;;
            deploy=*)
                set -- $(IFS==; echo $o)
                echo "Retrieve deployment configuration"
                set -- $(IFS==; echo $o)
                ip_addr=$(ip route get 1.0.0.0 | awk '{print $NF;exit}')
                role_init=$(wget -q "$2" -O - | jq -r ".deployment.\"$ip_addr\" | \"\(.role) \(.init)\"")
                set -- $(IFS=" "; echo $role_init)
                role=$1
                init=$2
                echo "role: $role"
                echo "init: $init"
                export stage2Init=$init
                mkdir -p /mnt-root/etc
                echo $role > /mnt-root/etc/role
                ;;
            role=*)
                set -- $(IFS==; echo $o)
                mkdir -p /mnt-root/etc
                echo "$2" > /mnt-root/etc/role
         esac
     done
     mkdir -p /mnt-root/root/.ssh/
     echo ${snakeOilPublicKey} >> /mnt-root/root/.ssh/authorized_keys
  '';
  system.build.kexec_tarball =
    pkgs.callPackage <nixpkgs/nixos/lib/make-system-tarball.nix> {
      storeContents = [{
        object = config.system.build.kexec_script;
        symlink = "/kexec_nixos";
      }];
      contents = [ ];
    };
}
