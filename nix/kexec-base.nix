{ pkgs, config, ... }: {
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
    mkdir -p /mnt-root/etc
    for o in $(cat /proc/cmdline); do
        case $o in
            server=*)
                set -- $(IFS==; echo $o)
                echo "$2 server" > /etc/hosts
                ;;
            deploy=*)
                echo "Retrieve deployment configuration"
                set -- $(IFS==; echo $o)
                ip_addr=$(ip route get 1.0.0.0 | awk '{print $NF;exit}')
                deployment_json="/mnt-root/etc/deployment.json"
                wget -q "$2" -O $deployment_json
                role_init=$(jq -r ".deployment.\"$ip_addr\" | \"\(.role) \(.init)\""  $deployment_json)
                set -- $(IFS=" "; echo $role_init)
                role=$1
                init=$2
                echo "role: $role"
                echo "init: $init"
                export stage2Init=$init
                echo $role > /mnt-root/etc/role
                ssh_key_pub=$(jq -r '."ssh_key.pub" // empty' $deployment_json)
                if [ ! -z "$ssh_key_pub" ]; then
                    mkdir -p /mnt-root/root/.ssh/
                    echo "$ssh_key_pub" >> /mnt-root/root/.ssh/authorized_keys
                fi
                echo "Generate /etc/hosts from deployment.json"
                jq -r '.deployment | to_entries | map(.key + " " + (.value.role)) | .[]' \
                $deployment_json >> /mnt-root/etc/hosts
                ;;
            role=*)
                set -- $(IFS==; echo $o)
                echo "$2" > /mnt-root/etc/role
                ;;
            hosts=*)
                echo "Generate /etc/hosts from kernel parameter"
                set -- $(IFS==; echo $o)
                set -- $(IFS=,; echo $2)
                for ip_host in "$@"
                do
                    set -- $(IFS=#; echo $ip_host)
                    echo "$1 $2" >> /mnt-root/etc/deployment-hosts
                done
                ;;
            ssh_key.pub=*)
                echo "Add SSH public key to root's authorized_keys"
                set -- $(IFS==; echo $o)
                mkdir -p /mnt-root/root/.ssh
                echo "$2" | base64 -d >> /mnt-root/root/.ssh/authorized_keys
                ;;
         esac
     done
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
