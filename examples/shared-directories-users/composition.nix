{ pkgs, ... }: {
  roles = let
    users = { names = ["user1" "user2"]; prefixHome = "/users"; };
  in
    {
      server = { ... }: {
        nxc.users = users;
        nxc.sharedDirs."/users".export = true;
      };
      storage =  { ... }: {
        nxc.sharedDirs."/data".export = true;
      };
      client = { ... }: {
        nxc.users = users;
        nxc.sharedDirs."/users".server = "server";
        nxc.sharedDirs."/data".server = "storage";
      };
    };
  testScript = ''
    storage.succeed('touch /data/foo')
    client.succeed('ls /data/foo')
    client.succeed('su - user1 -c "touch /users/user1/bar"')
    server.succeed('su - user1 -c "ls /users/user1/bar"')
  '';
}
