{ nixpkgs, mode, ... }:
composition:

let
  pkgs = (import nixpkgs) { };

  compositionSet = composition { pkgs = pkgs; };
  nodes = compositionSet.nodes;
  testScriptRaw =
    if compositionSet ? testScript then compositionSet.testScript else "";
  machines = builtins.attrNames nodes;

  # from nixpkgs/nixos/lib/testing-python.nix
  testScript =
    # Call the test script with the computed nodes.
    if pkgs.lib.isFunction testScriptRaw then
      testScriptRaw { inherit nodes; }
    else
      testScriptRaw;

  modeConfigOK = { lib, config, ... }: {
    imports = [
      <nixpkgs/nixos/modules/profiles/all-hardware.nix>
      <nixpkgs/nixos/modules/profiles/base.nix>
      <nixpkgs/nixos/modules/profiles/installation-device.nix>
      <nixpkgs/nixos/modules/installer/scan/not-detected.nix>
      ./netboot.nix
      ./kexec-base.nix
      #"${toString modulesPath}/testing/test-instrumentation.nix"
    ];
  };

  modeConfig = if mode == "kexec-vm" then
  #{ lib, config, ... }: { vm-shared-dir.enable = true; }
    import ./kexec-vm.nix
  else
    { lib, config, ... }: {
      imports = [
        <nixpkgs/nixos/modules/profiles/all-hardware.nix>
        <nixpkgs/nixos/modules/profiles/base.nix>
        <nixpkgs/nixos/modules/profiles/installation-device.nix>
        <nixpkgs/nixos/modules/installer/scan/not-detected.nix>
        ./netboot.nix
        ./kexec-base.nix
        #"${toString modulesPath}/testing/test-instrumentation.nix"
      ];
    };

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

  #sshKeys = import <nixpkgs/nixos/tests/ssh-keys.nix> pkgs;
  #snakeOilPrivateKey = sshKeys.snakeOilPrivateKey.text;
  #snakeOilPrivateKeyFile = pkgs.writeText "private-key" snakeOilPrivateKey;
  #snakeOilPublicKey = sshKeys.snakeOilPublicKey;

  kexecCommonConfig = { config, pkgs, lib, modulesPath, ... }: {

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
      kexec_info = {
        kernel = "${config.system.build.image}/kernel";
        initrd = "${config.system.build.image}/initrd";
        init = "${
            builtins.unsafeDiscardStringContext config.system.build.toplevel
          }/init";
        squashfs_img = "${config.system.build.squashfsStore}";
        qemu_script = "${kexec_qemu_script}";
        flavor_mode = "${mode}";
        #sshkey_priv = "${snakeOilPrivateKeyFile}";
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
          -append "loglevel=4 init=$INIT console=tty0 console=ttyS0,115200n8 $SERVER_IP $DEBUG_INITRD $DEPLOY $QEMU_APPEND " \
          -nographic \
          -device virtio-rng-pci \
          -device virtio-net-pci,netdev=vlan1,mac=52:54:00:12:01:$VM_ID \
          -netdev vde,id=vlan1,sock=$QEMU_VDE_SOCKET \
          -virtfs local,path=$SHARED_DIR,security_model=none,mount_tag=shared \
          $QEMU_OPTS
        '';
      };
    };
  };

  # 
  #

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
      modules = [ configuration kexecCommonConfig vmSharedDirMod modeConfig ];
    };

in let
  allConfig = pkgs.lib.mapAttrs buildOneconfig nodes;
  machinesKexecInfo =
    pkgs.lib.mapAttrs (n: m: m.config.system.build.kexec_info) allConfig;
  testScriptFile = pkgs.writeTextFile {
    name = "test-script";
    text = "${testScript}";
  };
in {
  ComposeInfoFile = pkgs.writeText "compose-info.json" (builtins.toJSON {
    nodes = machinesKexecInfo;
    test_script = testScriptFile;
  });
}
