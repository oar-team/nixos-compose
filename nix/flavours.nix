{
  vm = import ./flavours/vm.nix;
  nixos-test = import ./flavours/nixos-test.nix;
  nixos-test-driver = import ./flavours/nixos-test-driver.nix;
  nixos-test-ssh = import ./flavours/nixos-test-ssh.nix;
  kexec-g5k = import ./flavours/kexec-g5k.nix;
}
