{
  vm-ramdisk = import ./flavours/vm-ramdisk.nix;
  nixos-test = import ./flavours/nixos-test.nix;
  nixos-test-driver = import ./flavours/nixos-test-driver.nix;
  nixos-test-ssh = import ./flavours/nixos-test-ssh.nix;
  # vm = import ./flavour/vm.nix;
  # vm-bridged = import ./flavour/vm-bridged.nix;
  g5k-ramdisk = import ./flavours/g5k-ramdisk.nix;
  g5k-image = import ./flavours/g5k-image.nix;
  docker = import ./flavours/docker.nix;
  g5k-nfs-store = import ./flavours/g5k-nfs-store.nix;
}
