{ pkgs, ... }: {
  roles = {
    linux_5_15 = { pkgs, lib, ... }: {
      boot.kernelPackages = pkgs.linuxKernel.packages.linux_5_15;
    };
  };
  testScript = ''
    linux_5_15.succeed("uname -r | grep 5.15")
  '';
}
