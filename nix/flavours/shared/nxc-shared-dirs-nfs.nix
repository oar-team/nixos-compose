{ config, lib, ... }:
with lib;
let
  cfg = config.nxc;
  sharedDirs = attrNames cfg.sharedDirs;
  all_sharedDirsExport = builtins.filter (x: cfg.sharedDirs.${x}.export) sharedDirs;
  all_sharedDirsServers = builtins.filter (x: cfg.sharedDirs.${x}.server != "") sharedDirs;
in {
  config = mkMerge [
    # Create nfs server configurations and create directories
    (mkIf (cfg.sharedDirs != { } && all_sharedDirsExport != [ ]) {
      services.nfs.server.enable = true;
      services.nfs.server.exports = concatStrings (map
        (n: "${n} *(rw,no_subtree_check,fsid=0,no_root_squash)\n") all_sharedDirsExport);
      nxc.sharedDirsBootCommands = concatStrings (map
        (n: "mkdir -p ${n}" ) all_sharedDirsExport);
    })

    # Create nfs client configuration (/etc/fstab entries)
    (mkIf (cfg.sharedDirs != { } && all_sharedDirsServers != [ ] ) {
      fileSystems = builtins.listToAttrs (map
        (x: { name = x;
              value = {
                device = "${cfg.sharedDirs.${x}.server}:${x}";
                fsType = "nfs";
              };
            }) all_sharedDirsServers);
    })
  ];
}
