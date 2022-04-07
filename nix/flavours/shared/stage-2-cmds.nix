{ config, pkgs, ... }:
let
  unsafeSshKeys = import ./ssh-keys.nix;
  set_root_ssh_keys = if config.nxc.root-sshKeys.enable then ''
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
  boot.postBootCommands = ''
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
    nix_path_registration="/nix/store/nix-path-registration"
    if [[ -f "$nix_path_registration"-"$compositionName"-"$role" ]]; then
      nix_path_registration="$nix_path_registration"-"$compositionName"-"$role"
    fi
    echo "nix-store: load db $nix_path_registration"
    ${config.nix.package}/bin/nix-store --load-db < $nix_path_registration

    # nixos-rebuild also requires a "system" profile and an
    # /etc/NIXOS tag.
    touch /etc/NIXOS
    ${config.nix.package}/bin/nix-env -p /nix/var/nix/profiles/system --set /run/current-system

    ${config.nxc.postBootCommands}
  '';
}
