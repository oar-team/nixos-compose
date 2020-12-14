{ nixpkgs, mode, ... }:
composition:

let
  pkgs = (import nixpkgs) { };

  compositionSet = composition { pkgs = pkgs; };
  nodes = compositionSet.nodes;

  machines = builtins.attrNames nodes;

  configMode = if mode == "kexec-vm" then
    #{ lib, config, ... }: { vm-shared-dir.enable = true; }
    import ./kexec-vm.nix
  else
    { lib, config, ... }: { };

  vmSharedDirMod = { lib, config, ... }: {
    options = {
      vm-shared-dir = { enable = lib.mkEnableOption "a vm shared directory"; };
    };
    config = lib.mkIf config.vm-shared-dir.enable {
      fileSystems."/tmp/shared" = {
        device = "shared";
        fsType = "9p";
        options = [ "trans=virtio" "version=9p2000.L" ];
      };
    };
  };

  sshKeys = import <nixpkgs/nixos/tests/ssh-keys.nix> pkgs;
  snakeOilPrivateKey = sshKeys.snakeOilPrivateKey.text;
  snakeOilPrivateKeyFile = pkgs.writeText "private-key" snakeOilPrivateKey;
  snakeOilPublicKey = sshKeys.snakeOilPublicKey;

  kexecVmConfiguration = { config, pkgs, lib, modulesPath, ... }: {
    imports = [
      "${toString modulesPath}/profiles/minimal.nix"
      "${toString modulesPath}/profiles/qemu-guest.nix"
      ./base-hardware.nix
      ./installation-device.nix
      ./netboot.nix
      ./kexec-base.nix
      #"${toString modulesPath}/testing/test-instrumentation.nix"
    ];

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

    services.sshd.enable = true;
    services.mingetty.autologinUser = lib.mkDefault "root";
    security.polkit.enable = false; # to reduce initrd
    services.udisks2.enable = false; # to reduce initrd

    system.build = rec {
      kexec_info = {
        kernel = "${config.system.build.image}/kernel";
        initrd = "${config.system.build.image}/initrd";
        init = "${
            builtins.unsafeDiscardStringContext config.system.build.toplevel
          }/init";
        squashfs_img = "${config.system.build.squashfsStore}";
        qemu_script = "${kexec_qemu_script}";
        sshkey_priv = "${snakeOilPrivateKeyFile}";
      };

      kexec_qemu_script = pkgs.writeTextFile {
        executable = true;
        name = "kexec-qemu";
        text = ''
          #!/bin/sh

          : ''${NAME:=nixos}
          : ''${VM_ID:=1}
          : ''${MEM:=4096}
          : ''${TMPDIR:=/tmp}
          : ''${SHARED_DIR:=/tmp/shared-xchg}
          : ''${QEMU_VDE_SOCKET:=/tmp/kexec-qemu-vde1.ctl}
          : ''${SERVER_IP:=server=10.0.2.15}

          #if [ ! -S $QEMU_VDE_SOCKET/ctl ]; then 
          #  echo 'launch vde_switch'
          #  vde_switch -s $QEMU_VDE_SOCKET --dirmode 0700 &
          #  slirpvde -d -s /tmp/kexec-qemu-vde1.ctl -dhcp
          #fi

          mkdir -p /tmp/shared-xchg

          : ''${KERNEL=${config.system.build.image}/kernel}
          : ''${INITRD=${config.system.build.image}/initrd}
          : ''${INIT=${
            builtins.unsafeDiscardStringContext config.system.build.toplevel
          }/init}

          qemu-kvm -name $NAME -m $MEM -kernel $KERNEL -initrd $INITRD \
          -append "loglevel=4 init=$INIT console=tty0 console=ttyS0,115200n8 $SERVER_IP $DEBUG_INITRD $QEMU_APPEND" \
          -nographic \
          -device virtio-rng-pci \
          -virtfs local,path=$SHARED_DIR,security_model=none,mount_tag=shared \
          -device e1000,netdev=net0 \
          -netdev user,id=net0,hostfwd=tcp::5555-:22 \
          $QEMU_OPTS
        '';
      };
    };
  };

  #-device virtio-rng-pci \
  #-device virtio-net-pci,netdev=vlan1,mac=52:54:00:12:01:0$VM_ID \
  #-netdev vde,id=vlan1,sock=$QEMU_VDE_SOCKET \

  #  -vga std \

  #          -serial mon:telnet:127.0.0.1:700$VM_ID,server,nowait \
  #          - nographic -serial mon:stdio \
  #$QEMU_OPTS
  #-nographic -serial mon:stdio \
  #-vga std \
  #$QEMU_OPTS
  buildOneconfig = machine: configuration:
    import "${toString nixpkgs}/nixos/lib/eval-config.nix" {
      #inherit system;
      inherit pkgs;
      modules =
        [ configuration kexecVmConfiguration vmSharedDirMod configMode ];
    };

in let
  allConfig = pkgs.lib.mapAttrs buildOneconfig nodes;
  machinesKexecInfo =
    pkgs.lib.mapAttrs (n: m: m.config.system.build.kexec_info) allConfig;
in {
  machinesKexecInfoFile =
    pkgs.writeText "kexec-info.json" (builtins.toJSON machinesKexecInfo);
}
