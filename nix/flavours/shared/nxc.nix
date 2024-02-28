{ config, pkgs, lib, modulesPath, ... }:

with lib;
let
  cfg = config.nxc;
  helpers = import ../../helpers.nix;
  unsafeSshKeys = import ./ssh-keys.nix;
  set_root_ssh_keys = if cfg.root-sshKeys.enable then ''
    # set unsafe root keys
    echo "${unsafeSshKeys.snakeOilPrivateKey}" > /root/.ssh/id_rsa
    chmod 600 /root/.ssh/id_rsa
    echo "${unsafeSshKeys.snakeOilPublicKey}" > /root/.ssh/id_rsa.pub
    echo "${unsafeSshKeys.snakeOilPublicKey}" >> /root/.ssh/authorized_keys
    echo "Host *" > /root/.ssh/config
    echo "   StrictHostKeyChecking no" >> /root/.ssh/config
    echo "   HashKnownHosts no" >> /root/.ssh/config
  '' else "";

in
{
  options = {
    nxc = {
      qemu-script = {
        enable = mkEnableOption "Build qemu and qemu_script (take space)";
      };
      root-sshKeys = {
        enable = mkOption {
          type = types.bool;
          default = true;
          description = "Set root's ssh keys (add pub key to authorized_keys)";
        };
      };
      baseBootCommands = {
        enable = mkOption {
          type = types.bool;
          default = true;
          description = "Set hostname, nix-store database content registration";
        };
      };
      postBootCommands = mkOption {
        default = "";
        example = "touch /etc/foo";
        type = types.lines;
        description = ''
          Shell commands to be executed just before systemd is started.
        '';
      };
      wait-online = {
        enable = mkEnableOption "Wait to network is operational";
      };
      users = {
        names = mkOption {
          default = [ ];
          example =  ["user1" "user2"];
          type = types.listOf types.str;
          description = "List of user names";
        };
        prefixHome = mkOption {
          default = "/home";
          example = "/users";
          type = types.str;
          description = "Directory prefix of users' home";
        };
      };

      sharedDirs = mkOption {
        default = {};
        type = with types; attrsOf (submodule {
          options = {
            export = mkOption {
              type = types.bool;
              default = false;
              description = "";
            };
            server = mkOption {
               type = types.str;
               default = "";
               description = "";
            };
          };
        });
        example = {
          "/users".export = true;
        };
        description = "Shared directory (flavour dependent)";
      };
      sharedDirsBootCommands = mkOption {
        default = "";
        example = "touch /etc/foo";
        type = types.lines;
        description = ''
        '';
      };
    };
  };

  config =
    mkMerge [

    (mkIf (cfg.users.names != [ ]) {
      users.users = helpers.mapListToAttrs (n: { ${n} = { isNormalUser = true;
                                                          home = "${cfg.users.prefixHome}/${n}";
                                                          group = "users";
                                                          #openssh.authorizedKeys.keys = (import ./ssh-keys.nix).snakeOilPublicKey;
                                                        };
                                               }) cfg.users.names;})

    (mkIf cfg.wait-online.enable {
      systemd.services.nxc-network-wait-online = {
        after = [ "network.target" ];
        wantedBy = [ "multi-user.target" "network-online.target" ];
        serviceConfig.Type = "oneshot";
        script = ''
        # wait  network is ready
        while ! ${pkgs.iproute2}/bin/ip route get 1.0.0.0 ; do
        sleep .2
        done
        '';
      };
    })
    (mkIf cfg.baseBootCommands.enable {
      boot.postBootCommands = ''
        for o in $(cat /proc/cmdline); do
          case $o in
               ip=*)
                   set -- $(IFS==; echo $o)
                   set -- $(IFS=:; echo $2)
                   ip_addr="$1"
                   ${pkgs.iproute2}/bin/ip addr add $1/24 dev eth1
                   ;;
           esac
        done

        ln -s /run/current-system/sw/bin/bash /bin/bash
        compositionName=""
        if [[ -f /etc/nxc-composition ]]; then
          compositionName=$(cat /etc/nxc-composition)
        fi
        echo "composition name: $compositionName"

        hostname=""
        if [[ -f /etc/nxc/hostname ]]; then
          hostname=$(cat /etc/nxc/hostname)
        fi

        role=""
        if [[ -f /etc/nxc/role ]]; then
          role=$(cat /etc/nxc/role)
          if [[ -z $hostname ]]; then
            hostname=$role
          fi
        fi

        if [[ ! -z $hostname ]]; then
          echo "hostname name: $hostname"
          ${pkgs.inetutils}/bin/hostname $hostname
        fi

        # Add deployment's hosts if any
        if [[ -f /etc/nxc/deployment-hosts ]]; then
          rm -f /etc/hosts
          cat /etc/static/hosts > /etc/hosts
          cat /etc/nxc/deployment-hosts >> /etc/hosts
        fi

        mkdir -p /root/.ssh/
        chmod 700 /root/.ssh/
        ${set_root_ssh_keys}

        # Execute post boot scripts optionally provided through flavour/extraModules or composition
        for post_boot_script in $(ls -d /etc/post-boot-script* 2> /dev/null);
        do
          echo execute $post_boot_script
          $post_boot_script
        done

        # After booting, register the contents of the Nix store
        # in the Nix database in the tmpfs.

        if [ -d /etc/nxc/all_compositions_registration_store ]; then
          nix_path_registration="/etc/nxc/all_compositions_registration_store/nix-path-registration"
        else
          nix_path_registration="/nix/store/nix-path-registration"
        fi

        if [[ -f "$nix_path_registration"-"$compositionName"-"$role" ]]; then
          nix_path_registration="$nix_path_registration"-"$compositionName"-"$role"
        fi

        echo "nix-store: load db $nix_path_registration"
        #${config.nix.package}/bin/nix-store --load-db < $nix_path_registration

        #echo "inetutils"
        #echo ${pkgs.inetutils}/bin
        #exec /bin/bash

        # nixos-rebuild also requires a "system" profile and an
        # /etc/NIXOS tag.
        touch /etc/NIXOS
        # TODO can we remove it ?
        #${config.nix.package}/bin/nix-env -p /nix/var/nix/profiles/system --set /run/current-system

        ${
          if cfg.sharedDirsBootCommands != "" then
            cfg.sharedDirsBootCommands
          else
            ""
        }
        ${
          if cfg.users.names != [ ] then
            "chmod 755 ${cfg.users.prefixHome}"
            else ""
         }
        ${cfg.postBootCommands}
      '';})
      ];
}
