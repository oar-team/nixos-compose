{ config, lib, pkgs, ... }: {

  # FIXME: migration to systemd stage 1 required soon!
  # https://gitlab.inria.fr/nixos-compose/nixos-compose/-/issues/63
  boot.initrd.systemd.enable = !lib.versionAtLeast config.system.stateVersion "26.05";

  boot.initrd.extraUtilsCommands = ''
    copy_bin_and_libs ${pkgs.jq}/bin/jq
    copy_bin_and_libs ${pkgs.kexec-tools}/bin/kexec
  '';

  boot.initrd.postMountCommands = ''
    allowShell=1
    #echo Breakpoint reached && fail
    mkdir -p /mnt-root/etc/nxc

    ip a

    for o in $(cat /proc/cmdline); do
      case $o in
        flavour=*)
          set -- $(IFS==; echo $o)
          flavour="$2"
          echo "flavour: $flavour"
          ;;
        ip=*)
          set -- $(IFS==; echo $o)
          set -- $(IFS=:; echo $2)
          ip_addr="$1"
          ;;
      esac
    done

    echo "IPv4 address: $ip_addr "
    echo $ip_addr > /mnt-root/etc/nxc/ip_addr

    mkdir -p /mnt-root/nix/.ro-store
    mkdir -p /mnt-root/nix/.rw-store/work
    mkdir -p /mnt-root/nix/.rw-store/store
    mkdir -p /mnt-root/nix/store
    mkdir /nxc-composition

    echo "Mount host shared store: nix-store"

    mount -t 9p -o trans=virtio,version=9p2000.L,msize=16384,cache=loose nix-store /mnt-root/nix/.ro-store
    mount -t overlay overlay -o lowerdir=/mnt-root/nix/.ro-store,upperdir=/mnt-root/nix/.rw-store/store,workdir=/mnt-root/nix/.rw-store/work /mnt-root/nix/store

    echo "Mount host shared store: nxc-composition"
    mount -t 9p -o trans=virtio,version=9p2000.L,msize=16384,cache=loose nxc-composition /nxc-composition

    # cat /proc/cmdline
    # ls /nxc-composition

    for o in $(cat /proc/cmdline); do
      case $o in
        deploy=*)
          echo "Retrieve deployment configuration"
          deployment_json="/mnt-root/etc/nxc/deployment.json"
          set -- $(IFS==; echo $o)
          cp /nxc-composition/$2 $deployment_json
          umount nxc-composition
          ;;

        role=*)
          set -- $(IFS==; echo $o)
          echo "$2" > /mnt-root/etc/nxc/role
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

    compositions_info_file=$(jq -r '."compositions_info_path" // empty' $deployment_json)
    echo "compositions info file: $compositions_info_file"

    toplevel=$(jq -r ".\"$composition\".roles.\"$role\"" /mnt-root"$compositions_info_file")

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

    export stage2Init=$init
    echo $role > /mnt-root/etc/nxc/role
    echo $hostname >> /mnt-root/etc/nxc/hostname

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

    #echo Breakpoint reached  after && fail
  '';
}
