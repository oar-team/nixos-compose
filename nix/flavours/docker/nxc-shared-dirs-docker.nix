{ config, lib, ... }:
with lib;
let
  cfg = config.nxc;
  sharedDirs = attrNames cfg.sharedDirs;
  all_sharedDirsExport = builtins.filter (x: cfg.sharedDirs.${x}.export) sharedDirs;
  all_sharedDirsServer = builtins.filter (x: cfg.sharedDirs.${x}.server != "") sharedDirs;
in {
  config = mkIf (cfg.sharedDirs != {}) {
    nxc.sharedDirsBootCommands = concatStrings (map
      (n: ''
          if [[ -d /var/nxc/shared${n} ]]; then
            rm -rf /var/nxc/shared${n}/{*,.*}
          fi
          mkdir -p /var/nxc/shared${n}
          mv ${n}/{*,.*} /var/nxc/shared${n}
          mount --bind /var/nxc/shared${n} ${n}
      '') all_sharedDirsExport) + concatStrings (map
      (n: ''
          mkdir -p /var/nxc/shared${n}
          mount --bind /var/nxc/shared${n} ${n}
      '') all_sharedDirsServer);
  };
}
