{ pkgs, ... }: {
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
}
