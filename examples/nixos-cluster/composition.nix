{ pkgs, ... }:
let
  inherit (import ./ssh-keys.nix pkgs) snakeOilPrivateKey snakeOilPublicKey;

  commonConfig = { pkgs, ... }: {
    boot.postBootCommands = ''
      cp ${snakeOilPrivateKey} /root/.ssh/id_rsa
      chmod 600 /root/.ssh/id_rsa
      cp ${snakeOilPublicKey} /root/.ssh/id_rsa.pub
      cat ${snakeOilPublicKey} >> /root/.ssh/authorized_keys
      nix-store --generate-binary-cache-key builder /root/.ssh/id_rsa /root/.ssh/id_rsa.pub
    '';
    networking.firewall.enable = false;
    services.sshd.enable = true;
    services.openssh = {
      enable = true;
      ports = [ 22 ];
      permitRootLogin = "yes";
      authorizedKeysFiles = [ "${snakeOilPublicKey}" ];
    };
    users.users.root.password = "nixos";
  };

in {
  nodes = {
    builder = { pkgs, ... }: {
      imports = [ commonConfig ];
      services.nix-serve = {
        enable = true;
        port = 8080;
      };
      # nix.sshServe = {
      #   enable = true;
      #   keys = [ "/root/.ssh/id_rsa.pub" ];
      # };
    };
    node = { pkgs, ... }: {
      imports = [ commonConfig ];
      nix.binaryCaches = [ "http://builder:8080/" ];
      nix.requireSignedBinaryCaches = false;

      nix.buildMachines = [{
        hostName = "builder";
        system = "x86_64-linux";
        # if the builder supports building for multiple architectures, 
        # replace the previous line by, e.g.,
        # systems = ["x86_64-linux" "aarch64-linux"];
        maxJobs = 1;
        speedFactor = 2;
        supportedFeatures = [ "nixos-test" "benchmark" "big-parallel" "kvm" ];
        mandatoryFeatures = [ ];
      }];
      nix.distributedBuilds = true;
      # optional, useful when the builder has a faster internet connection than yours
      nix.extraOptions = ''
        builders-use-substitutes = true
      '';
    };
  };
  testScript = ''
    builder.succeed("true")
  '';
}
