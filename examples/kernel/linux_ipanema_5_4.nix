{ pkgs, ... }: {
  nodes = {
    linux_ipanema_5_4 = { pkgs, lib, ... }: {
      boot.kernelPackages = let
        linux_ipanema_pkg = { fetchgit, buildLinux, ... }@args:

          buildLinux (args // rec {
            version = "5.4.0";
            modDirVersion = version;

            src = fetchgit {
              url = "https://gitlab.inria.fr/ipanema-public/ipanema-kernel.git";
              rev = "73efe6cbd7d7450830ea36d55dbd2baabebe7eaf";
              sha256 = "sha256-gUDpkOUyezJs1LrlCqJq8Ky74bQPVqBMSgp+J1d4QBg=";
            };
            kernelPatches = [ ];

            #extraConfig = ''
            #  INTEL_SGX y
            #'';
          } // (args.argsOverride or { }));
        linux_ipanema = pkgs.callPackage linux_ipanema_pkg { };
      in pkgs.recurseIntoAttrs (pkgs.linuxPackagesFor linux_ipanema);
    };

  };
  testScript = ''
    linux_ipanema_5_4.succeed("true")
  '';
}
