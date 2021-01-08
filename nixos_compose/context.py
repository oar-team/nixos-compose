import os
import os.path as op
import sys

from io import open
from functools import update_wrapper

import click

CONTEXT_SETTINGS = dict(auto_envvar_prefix='nixos_compose',
                        help_option_names=['-h', '--help'])

def reraise(tp, value, tb=None):
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value

class Context(object):

    def __init__(self):
        self.current_dir = os.getcwd()
        self.verbose = False
        self.workdir = self.current_dir
        self.debug = False

    def log(self, msg, *args, **kwargs):
        """Logs a message to stdout."""
        if args:
            msg %= args
        kwargs.setdefault("file", sys.stdout)
        click.echo(msg, **kwargs)

    def wlog(self, msg, *args):
        """Logs a warning message to stderr."""
        self.log(click.style("Warning: %s" % msg, fg="yellow"), *args, file=sys.stderr)

    def glog(self, msg, *args):
        """Logs a green message."""
        self.log(click.style("%s" % msg, fg="green"), *args)

    def vlog(self, msg, *args):
        """Logs a message to stderr only if verbose is enabled."""
        if self.verbose:
            self.log(msg, *args, **{'file': sys.stderr})

    def handle_error(self):
        exc_type, exc_value, tb = sys.exc_info()
        if not self.debug:
            sys.stderr.write(u"\nError: %s\n" % exc_value)
            sys.exit(1)
        else:
            reraise(exc_type, exc_value, tb.tb_next)


def make_pass_decorator(ensure=False):
    def decorator(f):
        @click.pass_context
        def new_func(*args, **kwargs):
            ctx = args[0]
            if ensure:
                obj = ctx.ensure_object(Context)
            else:
                obj = ctx.find_object(Context)
            try:
                return ctx.invoke(f, obj, *args[1:], **kwargs)
            except:
                obj.handle_error()
        return update_wrapper(new_func, f)
    return decorator


pass_context = make_pass_decorator(ensure=True)
