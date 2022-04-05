{ pkgs, ... }:
let
  inherit (import ./ssh-keys.nix pkgs)
    snakeOilPrivateKey snakeOilPublicKey cachePub cachePriv;

  sshKeysConf = ''
    cp ${snakeOilPrivateKey} /root/.ssh/id_rsa
    chmod 600 /root/.ssh/id_rsa
    cp ${snakeOilPublicKey} /root/.ssh/id_rsa.pub
    cat ${snakeOilPublicKey} >> /root/.ssh/authorized_keys
  '';

  commonConfig = { pkgs, ... }: {
    networking.firewall.enable = false;
    services.sshd.enable = true;
    services.openssh = {
      enable = true;
      ports = [ 22 ];
      permitRootLogin = "yes";
      authorizedKeysFiles = [ "${snakeOilPublicKey}" ];
    };
    users.users.root.password = "nixos";
    environment.systemPackages = [ pkgs.git ];
  };

in {
  nodes = {
    builder = { pkgs, ... }: {
      imports = [ commonConfig ];
      boot.postBootCommands = ''
        ${sshKeysConf}
        echo "${cachePriv}" > /root/cache-priv-key.pem
        echo "${cachePub}" > /root/cache-pub-key.pem
        echo "secret-key-files = /root/cache-priv-key.pem" >> /etc/nix/nix.conf
        # systemctl restart nix-daemon
        nix sign-paths --all -k /root/cache-priv-key.pem
      '';
      services.nix-serve = {
        enable = true;
        port = 8080;
      };
    };

    node = { pkgs, ... }: {
      imports = [ commonConfig ];
      boot.postBootCommands = ''
        ${sshKeysConf}
      '';
      nix.binaryCaches = [ "http://builder:8080/" ];
      nix.requireSignedBinaryCaches = false;

      nix.buildMachines = [{
        hostName = "builder";
        system = "x86_64-linux";
        maxJobs = 1;
        speedFactor = 2;
        supportedFeatures = [ "nixos-test" "benchmark" "big-parallel" "kvm" ];
        mandatoryFeatures = [ ];
      }];
      nix.distributedBuilds = true;
      # optional, useful when the builder has a faster internet connection than yours
      nix.extraOptions = ''
        builders-use-substitutes = true
        experimental-features = nix-command flakes
      '';
      nix.settings.trusted-public-keys = [ "${cachePub}" ];
      nix.settings.substituters = [ "ssh-ng://builder" ];
    };
  };
  testScript = ''
    builder.succeed("true")
  '';
}
