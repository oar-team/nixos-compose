{ config, pkgs, lib, modulesPath, ... }: {
  imports = [
    "${modulesPath}/profiles/minimal.nix"
    "${modulesPath}/profiles/qemu-guest.nix"
    #./base-hardware.nix
    ./installation-device.nix
    ./nxc-shared-dirs-nfs.nix
  ];

  boot.initrd.availableKernelModules = [
    # SATA/PATA support.
    "ahci"

    "ata_piix"

    "sata_inic162x"
    "sata_nv"
    "sata_promise"
    "sata_qstor"
    "sata_sil"
    "sata_sil24"
    "sata_sis"
    "sata_svw"
    "sata_sx4"
    "sata_uli"
    "sata_via"
    "sata_vsc"

    # SCSI support (incomplete).
    "3w-9xxx"
    "3w-xxxx"
    "aic79xx"
    "aic7xxx"
    "arcmsr"

    # Virtio (QEMU, KVM etc.) support.
    "virtio_net"
    "virtio_pci"
    "virtio_blk"
    "virtio_scsi"
    "virtio_balloon"
    "virtio_console"

    # Hyper-V support.
    "hv_storvsc"

  ];

  # Include lots of firmware.
  #hardware.enableRedistributableFirmware = true;
  hardware.enableRedistributableFirmware = false;

  fileSystems."/tmp/shared" = {
    device = "shared";
    fsType = "9p";
    options = [ "trans=virtio" "version=9p2000.L" ];
  };
}
