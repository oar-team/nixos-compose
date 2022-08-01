import os
import os.path as op


def touch(fname, times=None):
    dirname = "/".join(fname.split("/")[:-1])
    if not op.exists(dirname):
        os.makedirs(dirname)
    with open(fname, "a"):
        os.utime(fname, times)
