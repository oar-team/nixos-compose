let
  # For extra determinism
  nixpkgs = builtins.fetchTarball {
    url =
      "https://github.com/NixOS/nixpkgs/archive/e9bdaba31748dc5d9f78c280f2582017b6bf0dd9.tar.gz";
    sha256 = "1rgkgir0l6m50yf0aih43ih4hs62f532yssg1xfa3j8v5pshsa6v";
  };

  __flavour = {
    name = "vm";
    image = {
      type = "ramdisk";
      distribution = "all-in-one";
    };
  };

  flavour = ./flavour-vm.nix;

  composition = { pkgs, ... }: {
    nodes = {
      server = { pkgs, ... }: {
        services.nginx = {
          enable = true;
          # a minimal site with one page
          virtualHosts.default = {
            root = pkgs.runCommand "testdir" { } ''
              mkdir "$out"
              echo hello world > "$out/index.html"
            '';
          };
        };
        networking.firewall.enable = false;
      };
      client = { ... }: { };
    };
    testScript = ''
      server.wait_for_unit("nginx.service")
      client.wait_for_unit("network.target")
      assert "hello world" in client.succeed("curl -sSf http://server/")
    '';
  };
in import ./nix/compose-ng.nix { inherit nixpkgs flavour composition; }
