{ pkgs, ... }: {
  nodes = {
    linux_5_4 = { pkgs, lib, ... }: {
      boot.kernelPackages = pkgs.linuxKernel.packages.linux_5_4;
    };
  };
  testScript = ''
    linux_5_4.succeed("true")
  '';
}
