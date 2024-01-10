#!/bin/sh -

#
# This file is a slightly modified version of lxc/config/init/common/lxc-net.in from LXC project
# License: GPL2.1
#

#distrosysconfdir="@NXC_DISTRO_SYSCONF@"
varrun="/run/nxc"
varlib="/var/lib"

# These can be overridden in @NXC_DISTRO_SYSCONF@/nxc
#   or in @NXC_DISTRO_SYSCONF@/nxc-net

USE_NXC_BRIDGE="true"
NXC_BRIDGE="nxc-br0"
NXC_BRIDGE_MAC="00:16:3e:00:00:00"
: "${NXC_ADDR=10.0.3.1}"
NXC_NETMASK="255.255.255.0"
: "${NXC_NETWORK=10.0.3.0/24}"
: "${NXC_DHCP_CONFILE:-/dev/null}"
: "${NXC_DHCP_RANGE=10.0.3.2,10.0.3.254}"
NXC_DHCP_MAX="253"
NXC_DHCP_PING="true"
NXC_DOMAIN=""
NXC_USE_NFT="true"

NXC_IPV6_ADDR=""
NXC_IPV6_MASK=""
NXC_IPV6_NETWORK=""
#NXC_IPV6_NAT="false"
NXC_IPV6_NAT="true"

#[ ! -f $distrosysconfdir/nxc ] || . $distrosysconfdir/nxc

use_nft() {
    [ -n "$NFT" ] && nft list ruleset > /dev/null 2>&1 && [ "$NXC_USE_NFT" = "true" ]
}

NFT="$(command -v nft)"
if ! use_nft; then
    use_iptables_lock="-w"
    iptables -w -L -n > /dev/null 2>&1 || use_iptables_lock=""
fi

_netmask2cidr ()
{
    # Assumes there's no "255." after a non-255 byte in the mask
    local x=${1##*255.}
    set -- 0^^^128^192^224^240^248^252^254^ $(( (${#1} - ${#x})*2 )) ${x%%.*}
    x=${1%%$3*}
    echo $(( $2 + (${#x}/4) ))
}

_ifdown() {
    ip addr flush dev ${NXC_BRIDGE}
    ip link set dev ${NXC_BRIDGE} down
}

_ifup() {
    MASK=$(_netmask2cidr ${NXC_NETMASK})
    CIDR_ADDR="${NXC_ADDR}/${MASK}"
    ip addr add ${CIDR_ADDR} broadcast + dev ${NXC_BRIDGE}
    ip link set dev ${NXC_BRIDGE} address $NXC_BRIDGE_MAC
    ip link set dev ${NXC_BRIDGE} up
}

start_ipv6() {
    NXC_IPV6_ARG=""
    if [ -n "$NXC_IPV6_ADDR" ] && [ -n "$NXC_IPV6_MASK" ] && [ -n "$NXC_IPV6_NETWORK" ]; then
        echo 1 > /proc/sys/net/ipv6/conf/all/forwarding
        echo 0 > /proc/sys/net/ipv6/conf/${NXC_BRIDGE}/autoconf
        ip -6 addr add dev ${NXC_BRIDGE} ${NXC_IPV6_ADDR}/${NXC_IPV6_MASK}
        NXC_IPV6_ARG="--dhcp-range=${NXC_IPV6_ADDR},ra-only --listen-address ${NXC_IPV6_ADDR}"
    fi
}

start_iptables() {
    start_ipv6
    if [ -n "$NXC_IPV6_ARG" ] && [ "$NXC_IPV6_NAT" = "true" ]; then
        ip6tables $use_iptables_lock -t nat -A POSTROUTING -s ${NXC_IPV6_NETWORK} ! -d ${NXC_IPV6_NETWORK} -j MASQUERADE
    fi
    iptables $use_iptables_lock -I INPUT -i ${NXC_BRIDGE} -p udp --dport 67 -j ACCEPT
    iptables $use_iptables_lock -I INPUT -i ${NXC_BRIDGE} -p tcp --dport 67 -j ACCEPT
    iptables $use_iptables_lock -I INPUT -i ${NXC_BRIDGE} -p udp --dport 53 -j ACCEPT
    iptables $use_iptables_lock -I INPUT -i ${NXC_BRIDGE} -p tcp --dport 53 -j ACCEPT
    iptables $use_iptables_lock -I FORWARD -i ${NXC_BRIDGE} -j ACCEPT
    iptables $use_iptables_lock -I FORWARD -o ${NXC_BRIDGE} -j ACCEPT
    iptables $use_iptables_lock -t nat -A POSTROUTING -s ${NXC_NETWORK} ! -d ${NXC_NETWORK} -j MASQUERADE
    iptables $use_iptables_lock -t mangle -A POSTROUTING -o ${NXC_BRIDGE} -p udp -m udp --dport 68 -j CHECKSUM --checksum-fill
}

start_nftables() {
    start_ipv6
    NFT_RULESET=""
    if [ -n "$NXC_IPV6_ARG" ] && [ "$NXC_IPV6_NAT" = "true" ]; then
        NFT_RULESET="${NFT_RULESET}
add table ip6 nxc;
flush table ip6 nxc;
add chain ip6 nxc postrouting { type nat hook postrouting priority 100; };
add rule ip6 nxc postrouting ip6 saddr ${NXC_IPV6_NETWORK} ip6 daddr != ${NXC_IPV6_NETWORK} counter masquerade;
"
    fi
    NFT_RULESET="${NFT_RULESET};
add table inet nxc;
flush table inet nxc;
add chain inet nxc input { type filter hook input priority 0; };
add rule inet nxc input iifname ${NXC_BRIDGE} udp dport { 53, 67 } accept;
add rule inet nxc input iifname ${NXC_BRIDGE} tcp dport { 53, 67 } accept;
add chain inet nxc forward { type filter hook forward priority 0; };
add rule inet nxc forward iifname ${NXC_BRIDGE} accept;
add rule inet nxc forward oifname ${NXC_BRIDGE} accept;
add table ip nxc;
flush table ip nxc;
add chain ip nxc postrouting { type nat hook postrouting priority 100; };
add rule ip nxc postrouting ip saddr ${NXC_NETWORK} ip daddr != ${NXC_NETWORK} counter masquerade"
    nft "${NFT_RULESET}"
}

start() {
    [ "x$USE_NXC_BRIDGE" = "xtrue" ] || { exit 0; }

    [ ! -f "${varrun}/network_up" ] || { echo "nxc-net is already running"; exit 1; }

    if [ -d /sys/class/net/${NXC_BRIDGE} ]; then
        stop force || true
    fi

    FAILED=1

    cleanup() {
        set +e
        if [ "$FAILED" = "1" ]; then
            echo "Failed to setup nxc-net." >&2
            stop force
            exit 1
        fi
    }

    trap cleanup EXIT HUP INT TERM
    set -e

    # set up the nxc network
    [ ! -d /sys/class/net/${NXC_BRIDGE} ] && ip link add dev ${NXC_BRIDGE} type bridge
    echo 1 > /proc/sys/net/ipv4/ip_forward
    echo 0 > /proc/sys/net/ipv6/conf/${NXC_BRIDGE}/accept_dad || true

    # if we are run from systemd on a system with selinux enabled,
    # the mkdir will create /run/nxc as init_var_run_t which dnsmasq
    # can't write its pid into, so we restorecon it (to var_run_t)
    if [ ! -d "${varrun}" ]; then
        mkdir -p "${varrun}"
        if command -v restorecon >/dev/null 2>&1; then
            restorecon "${varrun}"
        fi
    fi

    _ifup

    if use_nft; then
        start_nftables
    else
        start_iptables
    fi

    NXC_DOMAIN_ARG=""
    if [ -n "$NXC_DOMAIN" ]; then
        NXC_DOMAIN_ARG="-s $NXC_DOMAIN -S /$NXC_DOMAIN/"
    fi

    # nxc's dnsmasq should be hermetic and not read `/etc/dnsmasq.conf` (which
    # it does by default if `--conf-file` is not present
    NXC_DHCP_CONFILE_ARG="--conf-file=$NXC_DHCP_CONFILE"

    # https://lists.linuxcontainers.org/pipermail/lxc-devel/2014-October/010561.html
    for DNSMASQ_USER in nxc-dnsmasq dnsmasq nobody
    do
        if getent passwd ${DNSMASQ_USER} >/dev/null; then
            break
        fi
    done

    NXC_DHCP_PING_ARG=""
    if [ "x$NXC_DHCP_PING" = "xfalse" ]; then
        NXC_DHCP_PING_ARG="--no-ping"
    fi

    DNSMASQ_MISC_DIR="$varlib/misc"
    if [ ! -d "$DNSMASQ_MISC_DIR" ]; then
        mkdir -p "$DNSMASQ_MISC_DIR"
    fi

    dnsmasq $NXC_DHCP_CONFILE_ARG $NXC_DOMAIN_ARG $NXC_DHCP_PING_ARG -u ${DNSMASQ_USER} \
            --log-debug\
            --strict-order --bind-interfaces --pid-file="${varrun}"/dnsmasq.pid \
            --listen-address ${NXC_ADDR} --dhcp-range ${NXC_DHCP_RANGE} \
            --dhcp-lease-max=${NXC_DHCP_MAX} --dhcp-no-override \
            --except-interface=lo --interface=${NXC_BRIDGE} \
            --dhcp-leasefile="${DNSMASQ_MISC_DIR}"/dnsmasq.${NXC_BRIDGE}.leases \
            --dhcp-authoritative $NXC_IPV6_ARG || cleanup

    touch "${varrun}"/network_up
    FAILED=0
}

stop_iptables() {
    iptables $use_iptables_lock -D INPUT -i ${NXC_BRIDGE} -p udp --dport 67 -j ACCEPT
    iptables $use_iptables_lock -D INPUT -i ${NXC_BRIDGE} -p tcp --dport 67 -j ACCEPT
    iptables $use_iptables_lock -D INPUT -i ${NXC_BRIDGE} -p udp --dport 53 -j ACCEPT
    iptables $use_iptables_lock -D INPUT -i ${NXC_BRIDGE} -p tcp --dport 53 -j ACCEPT
    iptables $use_iptables_lock -D FORWARD -i ${NXC_BRIDGE} -j ACCEPT
    iptables $use_iptables_lock -D FORWARD -o ${NXC_BRIDGE} -j ACCEPT
    iptables $use_iptables_lock -t nat -D POSTROUTING -s ${NXC_NETWORK} ! -d ${NXC_NETWORK} -j MASQUERADE
    iptables $use_iptables_lock -t mangle -D POSTROUTING -o ${NXC_BRIDGE} -p udp -m udp --dport 68 -j CHECKSUM --checksum-fill
    if [ "$NXC_IPV6_NAT" = "true" ]; then
        ip6tables $use_iptables_lock -t nat -D POSTROUTING -s ${NXC_IPV6_NETWORK} ! -d ${NXC_IPV6_NETWORK} -j MASQUERADE
    fi
}

stop_nftables() {
    # Adding table before removing them is just to avoid
    # delete error for non-existent table
    NFT_RULESET="add table inet nxc;
delete table inet nxc;
add table ip nxc;
delete table ip nxc;
"
    if [ "$NXC_IPV6_NAT" = "true" ]; then
        NFT_RULESET="${NFT_RULESET};
add table ip6 nxc;
delete table ip6 nxc;"
    fi
    nft "${NFT_RULESET}"
}

stop() {
    [ "x$USE_NXC_BRIDGE" = "xtrue" ] || { exit 0; }

    [ -f "${varrun}/network_up" ] || [ "$1" = "force" ] || { echo "nxc-net isn't running"; exit 1; }

    if [ -d /sys/class/net/${NXC_BRIDGE} ]; then
        _ifdown
        if use_nft; then
            stop_nftables
        else
            stop_iptables
        fi

        pid=$(cat "${varrun}"/dnsmasq.pid 2>/dev/null) && kill -9 $pid
        rm -f "${varrun}"/dnsmasq.pid
        # if $NXC_BRIDGE has attached interfaces, don't destroy the bridge
        ls /sys/class/net/${NXC_BRIDGE}/brif/* > /dev/null 2>&1 || ip link delete ${NXC_BRIDGE}
    fi

    rm -f "${varrun}"/network_up
}

# See how we were called.
case "$1" in
    start)
        start
    ;;

    stop)
        stop
    ;;

    restart|reload|force-reload)
        $0 stop
        $0 start
    ;;

    *)
        echo "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 2
esac

exit $?
