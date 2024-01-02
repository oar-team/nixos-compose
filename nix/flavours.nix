{
  vm = import ./flavours/vm.nix;
  vm-ramdisk = import ./flavours/vm-ramdisk.nix;
  docker = import ./flavours/docker.nix;
  g5k-ramdisk = import ./flavours/g5k-ramdisk.nix;
  g5k-image = import ./flavours/g5k-image.nix;
  g5k-nfs-store = import ./flavours/g5k-nfs-store.nix;
  nspawn = import ./flavours/nspawn.nix;
}
