import os
import os.path as op
import shutil
import filecmp

import click


def touch(fname, times=None):
    dirname = "/".join(fname.split("/")[:-1])
    if not op.exists(dirname):
        os.makedirs(dirname)
    with open(fname, "a"):
        os.utime(fname, times)


def copy_file(srcname, dstname, preserve_symlinks=True):
    if preserve_symlinks and op.islink(srcname):
        if op.islink(dstname):
            os.unlink(dstname)
        else:
            os.remove(dstname)
        linkto = os.readlink(srcname)
        os.symlink(linkto, dstname)
    else:
        if op.islink(dstname):
            os.unlink(dstname)
        shutil.copy2(srcname, dstname)


def copy_tree(src, dest, overwrite=False, ignore_if_exists=[]):
    """
    Copy all files in the source path to the destination path.
    """
    if op.exists(dest) and not overwrite:
        raise click.ClickException("File exists : '%s'" % dest)
    create = click.style("   create", fg="green")
    # chmod = click.style("    chmod", fg="cyan")
    overwrite = click.style("overwrite", fg="yellow")
    identical = click.style("identical", fg="blue")
    ignore = click.style("   ignore", fg="magenta")
    cwd = os.getcwd() + "/"
    for path, dirs, files in os.walk(src):
        relative_path = path[len(src) :].lstrip(os.sep)
        if not op.exists(op.join(dest, relative_path)):
            os.mkdir(op.join(dest, relative_path))
        for filename in files:
            src_file_path = op.join(path, filename)
            dest_file_path = op.join(dest, relative_path, filename)
            if dest_file_path.startswith(cwd):
                fancy_relative_path = dest_file_path.replace(cwd, "")
            else:
                fancy_relative_path = dest_file_path
            if op.exists(dest_file_path):
                if filename in ignore_if_exists:
                    click.echo("   " + ignore + "  " + fancy_relative_path)
                elif filecmp.cmp(src_file_path, dest_file_path):
                    click.echo("   " + identical + "  " + fancy_relative_path)
                else:
                    click.echo("   " + overwrite + "  " + fancy_relative_path)
                    copy_file(src_file_path, dest_file_path)
            else:
                click.echo("   " + create + "  " + fancy_relative_path)
                copy_file(src_file_path, dest_file_path)
