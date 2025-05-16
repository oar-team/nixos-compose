{ config, pkgs, lib, modulesPath, ... }:

with lib; {

  boot.initrd.availableKernelModules =
    [ "ahci" "ehci_pci" "megaraid_sas" "sd_mod" "i40e" "mlx5_core" ];
  boot.kernelModules = [ "kvm-intel" ];

  users.users.root.password = "";

  networking.firewall.enable = false;

  services.sshd.enable = true;

  networking.hostName = mkDefault "";

  services.getty.autologinUser = mkDefault "root";

  security.polkit.enable = false; # to reduce initrd
  services.udisks2.enable = false; # to reduce initrd

  system.build = rec {
    # TODO move to netboot due to config.system.build.netbootRamdisk ?
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
    initClosureInfo = {
      init = "${
          builtins.unsafeDiscardStringContext config.system.build.toplevel
        }/init";
      closure_info =
        "${pkgs.closureInfo { rootPaths = config.system.build.toplevel; }}";
    };
    ramdiskInfo = {
      kernel = "${config.system.build.image}/kernel";
      initrd = "${config.system.build.image}/initrd";
      squashfs_img = "${config.system.build.squashfsStore}";
      qemu_script = "${qemu_script}";
      #sshkey_priv = "${snakeOilPrivateKeyFile}";
    }  // initClosureInfo;
    # TODO remove or add as option
    # also used by multiple_compositions
    qemu_script = if config.nxc.qemu-script.enable then pkgs.writeTextFile {
      executable = true;
      name = "qemu_script";
      text = ''
        #!/usr/bin/env bash

        : ''${NAME:=nixos}
        : ''${VM_ID:=1}
        : ''${MEM:=1024}
        : ''${TMPDIR:=/tmp}
        : ''${SHARED_DIR:=/tmp/shared-xchg}
        : ''${QEMU_VDE_SOCKET:=/tmp/kexec-qemu-vde1.ctl}
        : ''${ROLE:=}
        : ''${FLAVOUR:=}
        : ''${GRAPHIC:=0}
        : ''${SHARED_NIX_STORE_DIR:=/nix/store}
        : ''${MAX_LENGTH_APPEND:=2047}
        : ''${HOSTFWDPORT:=22021}
        : ''${SHARED_NXC_COMPOSITION_DIR=}

        if [ -z $SHARED_NXC_COMPOSITION_DIR ]; then
          echo "undefined SHARED_NXC_COMPOSITION_DIR"
          exit 1
        fi

        IP=""
        NIC_USER_SSH_FORWARD=""
        if [ -z $TAP ]; then
          IP="ip=192.168.1.$VM_ID:::::eth1"
          NIC_USER_SSH_FORWARD="-nic user,model=virtio-net-pci,hostfwd=tcp::$(($HOSTFWDPORT+$VM_ID))-:22"
        fi

        # zero padding: 2 digits vm_id
        VM_ID_PADDED=$(printf "%02d\n" $VM_ID)

        if [ ! -S $QEMU_VDE_SOCKET/ctl ]; then
           if [ -z $TAP ]; then
              echo 'launch vde_switch'
              vde_switch -s $QEMU_VDE_SOCKET --dirmode 0700 &
           else
              echo 'launch vde_switch w/ tap0 (sudo needed)'
              sudo vde_switch -tap tap0 -s $QEMU_VDE_SOCKET --dirmode 0770 --group users&
              sudo ip addr add 10.0.2.1/24 dev tap0
              sudo ip link set dev tap0 up
           fi
           slirpvde -d -s $QEMU_VDE_SOCKET  -dhcp
        fi

        mkdir -p /tmp/shared-xchg

        : ''${KERNEL=${config.system.build.kernel}/bzImage}
        : ''${INITRD=${config.system.build.initialRamdisk}/initrd}
        : ''${INIT=${
          builtins.unsafeDiscardStringContext config.system.build.toplevel
        }/init}

        if [[ $GRAPHIC == "0" ]]; then
           NOGRAPHIC="-nographic"
        fi

        APPEND="$IP net.ifnames=0 console=tty0 console=ttyS0,115200n8 $FLAVOUR $ROLE $DEBUG_INITRD $DEPLOY $QEMU_APPEND $ADDITIONAL_KERNEL_PARAMS"

        LENGTH_APPEND=''${#APPEND}
        echo "Length of kernel’s command-line parameters string: $LENGTH_APPEND"
        if (( $LENGTH_APPEND > $MAX_LENGTH_APPEND )); then
           echo "Length of kernel’s command-line parameters string is too large: $LENGTH_APPEND > $MAX_LENGTH_APPEND"
           exit 1
        fi

        QEMU=qemu-kvm
        if ! command -v $QEMU &> /dev/null; then
          echo "$QEMU command not found"
          QEMU=kvm
          if ! command -v $QEMU &> /dev/null; then
            echo "$QEMU command not found"
            exit 1
          fi
        fi

        $QEMU -name $NAME -m $MEM -kernel $KERNEL -initrd $INITRD \
        -append "$APPEND" \
        -device virtio-rng-pci \
        -device virtio-net-pci,netdev=vlan1,mac=52:54:00:12:01:$VM_ID_PADDED \
        -netdev vde,id=vlan1,sock=$QEMU_VDE_SOCKET \
        -net nic,netdev=user.0,model=virtio -netdev user,id=user.0,hostfwd=tcp::$(($HOSTFWDPORT+$VM_ID))-:22 \
        -virtfs local,path=$SHARED_DIR,security_model=none,mount_tag=shared \
        -virtfs local,path=$SHARED_NIX_STORE_DIR,security_model=none,mount_tag=nix-store \
        -virtfs local,path=$SHARED_NXC_COMPOSITION_DIR,security_model=none,mount_tag=nxc-composition \
        $NOGRAPHIC \
        $QEMU_OPTS
      '';
    } else "Disable_for_space_saving";
  };

  # misc
  key = "no-manual";

  documentation.enable = mkDefault false;

  documentation.nixos.enable = mkDefault false;
}
