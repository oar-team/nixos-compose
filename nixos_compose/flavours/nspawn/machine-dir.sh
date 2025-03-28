#!/bin/sh -

base_dir=/var/lib/machines

prepare() {
    machine=$1
    toplevel=$2
    if [[ -z "$machine" ]]; then
        echo "machine name required"
        exit 1
    fi
    if [[ -z "$toplevel" ]]; then
        echo "toplevel path required"
        exit 1
    fi
    machine_dir="$base_dir/$machine"

    if [ -d $machine_dir ]; then
       echo "$machine_dir already exists"
       exit 1
    fi
    mkdir -p $machine_dir
    cd $machine_dir
    # mkdir dev etc nix proc sbin sys
    #mkdir -p dev etc nix/store proc sbin sys run/wrappers home bin root usr var
    # dev proc sys
    mkdir -p etc nix/store sbin home bin root usr var run tmp

    mkdir -p etc/nxc
    echo $machine > etc/nxc/hostname

    ln -s $toplevel/etc/os-release etc/
    ln -s $toplevel/init sbin/

    mount --bind -o ro /nix/store $machine_dir/nix/store
}

remove() {
    machine=$1
    if [[ -z "$machine" ]]; then
        echo "machine name required"
        exit 1
    fi
    machine_dir="$base_dir/$machine"

    if [ ! -d $machine_dir ]; then
       echo "Warning $machine_dir does not exist"
       exit 0
    fi
    umount $machine_dir/nix/store
    #umount $machine_dir/run/wrappers
    #umount $machine_dir/run
    #umount $machine_dir/tmp

    cd $base_dir
    chattr -i $machine/var/empty
    rm -rf $machine
}

# See how we were called.
case "$1" in
    prepare)
        prepare "$2" "$3"
    ;;

    remove)
        remove "$2"
    ;;

    reprepare)
        $0 remove "$2"
        $0 prepare "$2" "$3"
    ;;

    *)
        echo "Usage: $0 {prepare|remove|reprepare}"
        exit 2
esac

exit $?
