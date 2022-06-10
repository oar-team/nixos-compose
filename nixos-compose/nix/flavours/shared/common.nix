{ config, pkgs, lib, modulesPath, ... }:

with lib; {

  boot.initrd.availableKernelModules =
    [ "ahci" "ehci_pci" "megaraid_sas" "sd_mod" "i40e" "mlx5_core" ];
  boot.kernelModules = [ "kvm-intel" ];

  systemd.services.sshd.wantedBy = mkForce [ "multi-user.target" ];
  networking.hostName = mkDefault "";

  # add second serial console
  #systemd.services."getty@ttyS1".enable = true;
  #systemd.services."serial-getty@ttyS1" = {
  #enable = true;
  #wantedBy = [ "getty.target" ]; # to start at boot
  #serviceConfig.Restart = "always"; # restart when session is closed
  #};

  services.sshd.enable = true;
  services.getty.autologinUser = mkDefault "root";

  security.polkit.enable = false; # to reduce initrd
  services.udisks2.enable = false; # to reduce initrd

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
    # also used by multipl_compositions
    qemu_script = if config.nxc.qemu-script.enable then pkgs.writeTextFile {
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
        : ''${GRAPHIC:=0}

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

        if [[ $GRAPHIC == "0" ]]; then
           NOGRAPHIC="-nographic"
        fi

        qemu-kvm -name $NAME -m $MEM -kernel $KERNEL -initrd $INITRD \
        -append "loglevel=4 init=$INIT console=tty0 console=ttyS0,115200n8 $ROLE $SERVER_IP $DEBUG_INITRD $DEPLOY $QEMU_APPEND " \
        -device virtio-rng-pci \
        -device virtio-net-pci,netdev=vlan1,mac=52:54:00:12:01:$VM_ID \
        -netdev vde,id=vlan1,sock=$QEMU_VDE_SOCKET \
        -virtfs local,path=$SHARED_DIR,security_model=none,mount_tag=shared \
        $NOGRAPHIC \
        $QEMU_OPTS
      '';
    } else "Disable_for_space_saving";
  };

  # misc
  key = "no-manual";

  environment.noXlibs = mkDefault true;

  # This isn't perfect, but let's expect the user specifies an UTF-8 defaultLocale
  #i18n.supportedLocales = [ (config.i18n.defaultLocale + "/UTF-8") ];
  i18n.defaultLocale = "en_US.UTF-8";

  documentation.enable = mkDefault false;

  documentation.nixos.enable = mkDefault false;
}
