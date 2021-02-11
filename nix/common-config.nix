flavour:
{ config, pkgs, lib, modulesPath, ... }: {

  boot.loader.grub.enable = false;
  #boot.kernelParams = [
  #  "console=ttyS0,115200"
  #  "panic=30"
  #  "boot.panic_on_fail" # reboot the machine upon fatal boot issues
  #];

  # TODO lib.versionAtLeast pkgs.lib.version "20.09" (under 20.09 mount overlay explicitly
  fileSystems."/nix/store" = {
    fsType = "overlay";
    device = "overlay";
    options = [
      "lowerdir=/nix/.ro-store"
      "upperdir=/nix/.rw-store/store"
      "workdir=/nix/.rw-store/work"
    ];
  };

  systemd.services.sshd.wantedBy = lib.mkForce [ "multi-user.target" ];
  networking.hostName = lib.mkDefault "";

  # add second serial console
  #systemd.services."getty@ttyS1".enable = true;
  #systemd.services."serial-getty@ttyS1" = {
  #enable = true;
  #wantedBy = [ "getty.target" ]; # to start at boot
  #serviceConfig.Restart = "always"; # restart when session is closed
  #};

  boot.initrd.availableKernelModules =
    [ "ahci" "ehci_pci" "megaraid_sas" "sd_mod" "i40e" "mlx5_core" ];
  boot.kernelModules = [ "kvm-intel" ];

  services.sshd.enable = true;
  services.mingetty.autologinUser = lib.mkDefault "root";
  security.polkit.enable = false; # to reduce initrd
  services.udisks2.enable = false; # to reduce initrd

  system.build = rec {
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
    } // initClosureInfo;

    qemu_script = pkgs.writeTextFile {
      executable = true;
      name = "qemu_script";
      text = ''
        #!/bin/sh

        : ''${NAME:=nixos}
        : ''${VM_ID:=1}
        : ''${MEM:=4096}
        : ''${TMPDIR:=/tmp}
        : ''${SHARED_DIR:=/tmp/shared-xchg}
        : ''${QEMU_VDE_SOCKET:=/tmp/kexec-qemu-vde1.ctl}
        : ''${SERVER_IP:=server=10.0.2.15}
        : ''${ROLE:=}

        # zero padding: 2 digits vm_id
        VM_ID=$(printf "%02d\n" $VM_ID)

        if [[ $DEPLOY == "1" ]]; then
           DEPLOY="deploy=http://10.0.2.1:8000/deployment.json"
           TAP=1
        fi

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

        : ''${KERNEL=${config.system.build.image}/kernel}
        : ''${INITRD=${config.system.build.image}/initrd}
        : ''${INIT=${
          builtins.unsafeDiscardStringContext config.system.build.toplevel
        }/init}

        qemu-kvm -name $NAME -m $MEM -kernel $KERNEL -initrd $INITRD \
        -append "loglevel=4 init=$INIT console=tty0 console=ttyS0,115200n8 $ROLE $SERVER_IP $DEBUG_INITRD $DEPLOY $QEMU_APPEND " \
        -nographic \
        -device virtio-rng-pci \
        -device virtio-net-pci,netdev=vlan1,mac=52:54:00:12:01:$VM_ID \
        -netdev vde,id=vlan1,sock=$QEMU_VDE_SOCKET \
        -virtfs local,path=$SHARED_DIR,security_model=none,mount_tag=shared \
        $QEMU_OPTS
      '';
    };
  };
}
