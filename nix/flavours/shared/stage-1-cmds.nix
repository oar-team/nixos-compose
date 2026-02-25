{ lib, pkgs, ... }: {

  # boot.initrd.network.enable = true;

  # nxc users might set `networking.useDHCP` to false
  # but nxc deployment stage 1 must have dhcp
  boot.initrd.network.udhcpc.enable = lib.mkForce true;

  boot.initrd.extraUtilsCommands = ''
    copy_bin_and_libs ${pkgs.jq}/bin/jq
    copy_bin_and_libs ${pkgs.kexec-tools}/bin/kexec
    cp -pv ${pkgs.glibc}/lib/libnss_files.so.2 $out/lib
    cp -pv ${pkgs.glibc}/lib/libresolv.so.2 $out/lib
    cp -pv ${pkgs.glibc}/lib/libnss_dns.so.2 $out/lib
  '';

  boot.initrd.postMountCommands = ''
       allowShell=1
       #set -xv
       #echo Breakpoint reached && fail
       mkdir -p /mnt-root/etc/nxc

       set -- $(IFS=' '; echo $(ip route get 1.0.0.0))
       ip_addr=$7
       echo $ip_addr > /mnt-root/etc/nxc/ip_addr

       for o in $(cat /proc/cmdline); do
         case $o in
           nfs_store=*)
             set -- $(IFS==; echo $o)
             nfs_store="$2"
             echo "nfs_store: $nfs_store"
             ;;
           flavour=*)
             set -- $(IFS==; echo $o)
             flavour="$2"
             echo "flavour: $flavour"
             ;;
         esac
        done

       if [ "''${nfs_store+set}" = set ]; then
         mkdir -p /mnt-root/nix/.server-ro-store
         mkdir -p /mnt-root/nix/.rw-store/work
         mkdir -p /mnt-root/nix/.rw-store/store
         mkdir -p /mnt-root/nix/store

         echo "Mount NFS store: $nfs_store"

         mount -t nfs -o vers=3,nolock,ro,soft,retry=10 $nfs_store /mnt-root/nix/.server-ro-store

         mount -t overlay overlay -o lowerdir=/mnt-root/nix/.server-ro-store,upperdir=/mnt-root/nix/.rw-store/store,workdir=/mnt-root/nix/.rw-store/work /mnt-root/nix/store
       fi

       if [ "''${flavour+set}" = set ] && [ $flavour == "vm" ];then
         mkdir -p /mnt-root/nix/.ro-store
         mkdir -p /mnt-root/nix/.rw-store/work
         mkdir -p /mnt-root/nix/.rw-store/store
         mkdir -p /mnt-root/nix/store

        echo "Mount host shared store: nix-store"

        mount -t 9p -o trans=virtio,version=9p2000.L,msize=16384,cache=loose nix-store /mnt-root/nix/.ro-store

        mount -t overlay overlay -o lowerdir=/mnt-root/nix/.ro-store,upperdir=/mnt-root/nix/.rw-store/store,workdir=/mnt-root/nix/.rw-store/work /mnt-root/nix/store
       fi

       for o in $(cat /proc/cmdline); do
           case $o in
               server=*)
                   set -- $(IFS==; echo $o)
                   echo "$2 server" >> /mnt-root/etc/nxc/deployment-hosts
                   ;;
               deploy=*)
                   echo "Retrieve deployment configuration"
                   deployment_json="/mnt-root/etc/nxc/deployment.json"
                   ip_addr=$(ip route get 1.0.0.0 | awk '{print $NF;exit}')
                   d=$(echo $o | cut -c8-)
                   set -- $(IFS=:; echo $d)
                   if [ $1 == "https" ] || [ $1 == "http" ]
                   then
                      echo "Use http(s) to get deployment configuration at $d"
                      wget -q "$d" -O $deployment_json
                   else
                      echo "Use base64 decode to deployment configuration"
                      echo "$d" | base64 -d >> $deployment_json
                   fi
                   ;;

               role=*)
                   set -- $(IFS==; echo $o)
                   echo "$2" > /mnt-root/etc/nxc/role
                   ;;
               hosts=*)
                   echo "Generate /etc/nxc/deployment-hosts from kernel parameter"
                   set -- $(IFS==; echo $o)
                   set -- $(IFS=,; echo $2)
                   for ip_host in "$@"
                   do
                       set -- $(IFS=#; echo $ip_host)
                       echo "$1 $2" >> /mnt-root/etc/nxc/deployment-hosts
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

        composition=$(jq -r '."composition" // empty' $deployment_json)
        echo "composition: $composition"
        role_host=$(jq -r ".deployment.\"$ip_addr\" | \"\(.role) \(.host // \"\")\""  $deployment_json)
        set -- $(IFS=" "; echo $role_host)
        role=$1
        hostname=$2
        echo "role: $role"
        echo "hostname: $hostname"

        toplevel=""
        if [ "''${composition+set}" = set ]; then
           if [ -f /mnt-root/nix/store/compositions-info.json ]; then
              echo "/mnt-root/nix/store/compositions-info.json"
              toplevel=$(jq -r ".\"$composition\".roles.\"$role\"" /mnt-root/nix/store/compositions-info.json)
           else
              compositions_info_file=$(jq -r '."compositions_info_path" // empty' $deployment_json)
              echo "compositions info file: $compositions_info_file"
              toplevel=$(jq -r ".\"$composition\".roles.\"$role\"" /mnt-root/$compositions_info_file)
           fi
           echo "toplevel: $toplevel"
        fi

        for o in $(cat /proc/cmdline); do
          case $o in
            check_kernel_initrd)
              kernel_target=$(readlink /mnt-root"$toplevel"/kernel)
              initrd_target=$(readlink /mnt-root"$toplevel"/initrd)

              copy_base_kernel=$(jq -r ".all.kernel" $deployment_json)
              base_initrd=$(jq -r ".all.initrd" $deployment_json)

              base_kernel=$(cat /mnt-root"$copy_base_kernel"_store_path)

              echo kernel: $kernel_target $base_kernel
              echo initrd: $base_initrd $base_initrd
              #echo Breakpoint reached && fail

              if [ "$kernel_target" != "$base_kernel" ] || [ "$initrd_target" != "$base_initrd" ]; then
                  echo "Kexec to kernel/initrd target"
                  kexec -l /mnt-root"$kernel_target" --initrd=/mnt-root"$initrd_target"  --command-line="$(cat /proc/cmdline | sed -r 's/check_kernel_initrd//')"
                  kexec -e
              fi
              ;;
          esac
        done

        init="$toplevel"/init
        echo "init: $init"

        export stage2Init="$init"
        echo $role > /mnt-root/etc/nxc/role

        if   [ "''${hostname+set}" = set ]; then
             echo "$hostname" > /mnt-root/etc/nxc/hostname
        fi

        ssh_key_pub=$(jq -r '."ssh_key.pub" // empty' $deployment_json)

        if [ "''${ssh_key_pub+set}" = set ]; then
            mkdir -p /mnt-root/root/.ssh/
            echo "$ssh_key_pub" >> /mnt-root/root/.ssh/authorized_keys
        fi
        echo "Generate/complete /etc/nxc/deployment-hosts  from deployment.json"
        jq -r '.deployment | to_entries | map(.key + " " + (.value.host)) | .[]' \
        $deployment_json >> /mnt-root/etc/nxc/deployment-hosts

        echo "Retrieve all_compositions_registration_store_path"
        registration_store_path=$(jq -r '."all" | ."all_compositions_registration_store_path" // empty' $deployment_json)
        if [ "''${registration_store_path}" = set ]; then
          echo "Create link to $registration_store_path in /etc/nxc"
          # link destination will valid after switch_root
          ln -s "$registration_store_path" /mnt-root/etc/nxc/all_compositions_registration_store
        fi

     '';
}
