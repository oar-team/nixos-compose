{
  vm-ramdisk = import ./flavours/vm-ramdisk.nix;
  nixos-test = import ./flavours/nixos-test.nix;
  nixos-test-driver = import ./flavours/nixos-test-driver.nix;
  nixos-test-ssh = import ./flavours/nixos-test-ssh.nix;
  g5k-ramdisk = import ./flavours/g5k-ramdisk.nix;
}
