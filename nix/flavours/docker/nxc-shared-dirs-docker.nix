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
          if [[ -d /tmp/shared${n} ]]; then
            rm -rf /tmp/shared${n}/{*,.*}
          fi
          mkdir -p /tmp/shared${n}
          mv ${n}/{*,.*} /tmp/shared${n}
          rm -rf ${n}
          ln -s /tmp/shared${n} ${n}
      '') all_sharedDirsExport) + concatStrings (map
      (n: ''
          mkdir -p /tmp/shared${n}
          rm -rf ${n}
          ln -s /tmp/shared${n} ${n}
      '') all_sharedDirsServer);
  };
}
