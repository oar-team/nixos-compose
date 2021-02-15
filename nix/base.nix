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
  };

  boot.initrd.postMountCommands = ''
    mkdir -p /mnt-root/etc

    set -- $(IFS=' '; echo $(ip route get 1.0.0.0))
    ip_addr=$7
    echo $ip_addr > /mnt-root/etc/ip_addr

    for o in $(cat /proc/cmdline); do
        case $o in
            server=*)
                set -- $(IFS==; echo $o)
                echo "$2 server" > /etc/hosts
                ;;
            deploy:*)
                echo "Retrieve deployment configuration"
                deployment_json="/mnt-root/etc/deployment.json"
                ip_addr=$(ip route get 1.0.0.0 | awk '{print $NF;exit}')
                set -- $(IFS=:; echo $o)
                h=$(echo $2 | head -c 7)
                if [ $h == "https:/" ] || [ $h == "http://" ]
                then
                   echo "Use http(s) to get deployment configuration"
                   wget -q "$2" -O $deployment_json
                else
                   echo "Use base64 decode to deployment configuration"
                   echo "$2" | base64 -d >> $deployment_json
                fi
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
                $deployment_json >> /mnt-root/etc/deployment-hosts
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
            ssh_key.pub:*)
                echo "Add SSH public key to root's authorized_keys"
                set -- $(IFS=:; echo $o)
                mkdir -p /mnt-root/root/.ssh
                echo "$2" | base64 -d >> /mnt-root/root/.ssh/authorized_keys
                ;;
         esac
     done
  '';
}
