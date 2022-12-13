{ config, lib, ... }:
with lib;
let
  cfg = config.nxc;
  sharedDirs = attrNames cfg.sharedDirs;
  any_sharedDirsExport = builtins.any (x: x.export) (builtins.attrValues cfg.sharedDirs);
  any_sharedDirsServer = builtins.any (x: x.server != "") (builtins.attrValues cfg.sharedDirs);
  all_sharedDirsServers = builtins.filter (x: cfg.sharedDirs.${x}.server != "") sharedDirs;
in {
  config = mkMerge [
    (mkIf (cfg.sharedDirs != {} && any_sharedDirsExport) {
      services.nfs.server.enable = true;
      services.nfs.server.exports = concatStrings (map (n: "${n} *(rw,no_subtree_check,fsid=0,no_root_squash)\n") (builtins.filter (x: cfg.sharedDirs.${x}.export) sharedDirs) );
    })

    (mkIf (cfg.sharedDirs != {} && any_sharedDirsServer) {
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
