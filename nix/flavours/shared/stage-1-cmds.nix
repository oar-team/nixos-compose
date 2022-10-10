{ pkgs, config, ... }: {

  boot.initrd.network.enable = true;
  boot.initrd.extraUtilsCommands = ''
    copy_bin_and_libs ${pkgs.jq}/bin/jq
    cp -pv ${pkgs.glibc}/lib/libnss_files.so.2 $out/lib
    cp -pv ${pkgs.glibc}/lib/libresolv.so.2 $out/lib
    cp -pv ${pkgs.glibc}/lib/libnss_dns.so.2 $out/lib
  '';

  boot.initrd.postMountCommands = ''
       allowShell=1

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
                   composition=$(jq -r '."composition" // empty' $deployment_json)
                   echo "composition: $composition"
                   role_host=$(jq -r ".deployment.\"$ip_addr\" | \"\(.role) \(.host // \"\")\""  $deployment_json)
                   set -- $(IFS=" "; echo $role_host)
                   role=$1
                   hostname=$2
                   echo "role: $role"
                   echo "hostname: $hostname"

                   init=""
                   if  [ ! -z $composition ]; then
                      if [ -f /mnt-root/nix/store/compositions-info.json ]; then
                         echo "/mnt-root/nix/store/compositions-info.json"
                         init=$(jq -r ".\"$composition\".nodes.\"$role\".init" /mnt-root/nix/store/compositions-info.json)
                      else
                         compositions_info_file=$(jq -r '."compositions_info_path" // empty' $deployment_json)
                         echo "compositions info file: $compositions_info_file"
                         init=$(jq -r ".\"$composition\".nodes.\"$role\".init" /mnt-root/$compositions_info_file)
                      fi
                      echo "init: $init"
                   fi
                   export stage2Init=$init
                   echo $role > /mnt-root/etc/nxc/role
                   if  [ ! -z $hostname ]; then
                       echo $hostname >> /mnt-root/etc/nxc/hostname
                   fi
                   ssh_key_pub=$(jq -r '."ssh_key.pub" // empty' $deployment_json)
                   if [ ! -z "$ssh_key_pub" ]; then
                       mkdir -p /mnt-root/root/.ssh/
                       echo "$ssh_key_pub" >> /mnt-root/root/.ssh/authorized_keys
                   fi
                   echo "Generate/complete /etc/nxc/deployment-hosts  from deployment.json"
                   jq -r '.deployment | to_entries | map(.key + " " + (.value.host)) | .[]' \
                   $deployment_json >> /mnt-root/etc/nxc/deployment-hosts

                   echo "Retrieve all_compositions_registration_store_path"
                   registration_store_path=$(jq -r '."all" | ."all_compositions_registration_store_path" // empty' $deployment_json)
                   if [ ! -z "$registration_store_path" ]; then
                     echo "Create link to $registration_store_path in /etc/nxc"
                     # link destination will valid after switch_root
                     ln -s "$registration_store_path" /mnt-root/etc/nxc/all_compositions_registration_store
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

    #echo Breakpoint reached && fail
     '';
}
