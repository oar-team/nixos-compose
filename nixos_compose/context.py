import os
import sys
import time

import json
import yaml

from io import open
from functools import update_wrapper

import click

from .platform import Grid5000Platform
from .default_role import get_nxc_loader
from halo import Halo

# from .state import State

CONTEXT_SETTINGS = dict(
    auto_envvar_prefix="nixos_compose", help_option_names=["-h", "--help"]
)


def reraise(tp, value, tb=None):
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


class LazySpinner(object):
    def __init__(self):
        self.halo_spinner = None

    def create_if_needed(self):
        if not self.halo_spinner:
            self.halo_spinner = Halo(spinner="dots")

    def start(self, *args):
        self.create_if_needed()
        self.halo_spinner.start(*args)

    def succeed(self, *args):
        self.create_if_needed()
        self.halo_spinner.succeed(*args)

    def text(self, text):
        self.create_if_needed()
        self.halo_spinner.text = text


class Context(object):
    def __init__(self):
        self.t0 = time.time()
        self.nxc_file = None
        self.nxc = None
        self.envdir = None
        self.current_dir = os.getcwd()  # TOREMOVE ?
        self.verbose = False
        self.workdir = self.current_dir  # TOREMOVE ?
        self.debug = False
        self.prefix = "nxc"
        self.flavour = None
        self.composition_name = None
        self.composition_flavour_prefix = None  # REMOVE _prefix ???
        self.compose_info_file = None  # change to compositions_file ?
        self.compose_info = None  # change to compositioin of merge w/ compositionS ?
        self.multiple_compositions = False
        self.compositions_info = None  # Rename to compositions_flavour ????
        self.deployment_filename: str = ""
        self.deployment_info = None  # change to deployment ?
        self.deployment_info_b64 = ""  # change to depolyment_b64 ?
        self.ip_addresses = []
        self.host2ip_address = {}
        self.ssh = ""
        self.sudo = ""
        self.push_path = None
        self.interactive = False
        self.execute_test_script = False
        self.platform = None
        self.use_httpd = False
        self.httpd = None
        self.alternative_stores = [
            f"{os.environ['HOME']}/.local/share/nix/root/nix",
            f"{os.environ['HOME']}/.nix",
        ]

        self.roles_distribution = {}
        self.setup = None
        self.sigwait = None
        self.kernel_params = None
        self.all_started: bool = False
        self.no_start: bool = False  # use w/ driver CLI command which must not start machines
        self.external_connect: bool = False
        self.vde_tap: bool = False  # use to add tap interface which allow external IP
        # access either done by port forwarding on local
        # interface
        self.spinner = LazySpinner()
        self.show_spinner = True

    def init_workdir(self, env_name, env_id):
        with open(self.env_name_file, "w+") as fd:
            fd.write(env_name + "\n")
        if not os.path.exists(self.env_id_file):
            with open(self.env_id_file, "w+") as fd:
                fd.write(env_id + "\n")

    #    @property
    #    def state(self):
    #        if not hasattr(self, "_state"):
    #            self._state = State(self, state_file=self.state_file)
    #        return self._state
    #
    #    def update(self):
    #        self.state_file = op.join(self.envdir, "state.json")
    #        if "platform" in self.state:
    #            if self.state["platform"] == "Grid5000":
    #                self.platform = Grid5000Platform(self)

    def assert_valid_env(self):
        if not os.path.isdir(self.envdir):
            raise click.ClickException(
                "Missing nixos composition environment directory."
                " Run `nxc init` to create"
                " a new composition environment "
            )

    def log(self, msg, *args, **kwargs):
        """Logs a message to stdout."""
        if args:
            msg %= args
        kwargs.setdefault("file", sys.stdout)
        click.echo(msg, **kwargs)

    def wlog(self, msg, *args):
        """Logs a warning message to stderr."""
        self.log(click.style("Warning: %s" % msg, fg="yellow"), *args, file=sys.stderr)

    def elog(self, msg, *args):
        """Logs a error message to stderr."""
        self.log(click.style("Error: %s" % msg, fg="red"), *args, file=sys.stderr)

    def glog(self, msg, *args):
        """Logs a green message."""
        self.log(click.style("%s" % msg, fg="green"), *args)

    def vlog(self, msg, *args):
        """Logs a message to stderr only if verbose is enabled."""
        if self.verbose:
            self.log(msg, *args, **{"file": sys.stderr})

    def handle_error(self, exception):
        exc_type, exc_value, tb = sys.exc_info()
        if not self.debug:
            sys.stderr.write(f"\nError: {exc_value}, exception {exception}\n")
            sys.exit(1)
        else:
            reraise(exc_type, exc_value, tb.tb_next)

    def elapsed_time(self):
        return time.time() - self.t0

    def show_elapsed_time(self):
        duration = "{:.2f}".format(self.elapsed_time())
        self.vlog("Elapsed Time: " + (click.style(duration, fg="green")) + " seconds")

    def load_nxc(self, f):
        self.nxc = json.load(f)
        if "platform" in self.nxc and self.nxc["platform"] == "Grid5000":
            self.platform = Grid5000Platform(self)

    def set_roles_distribution(self, role_distribution_options, filename):
        roles_distribution = {}
        if filename:
            filename_tuple = os.path.splitext(filename)
            extension = filename_tuple[1]

            with open(filename, "r") as roles_f:
                if extension in [".yaml", ".yml"]:
                    roles_distribution = yaml.load(roles_f, Loader=get_nxc_loader())
                else:
                    roles_distribution = json.load(roles_f)

        # expend hostname role is associated to an integer
        for role, quantity in roles_distribution.items():
            try:
                roles_distribution[role] = [
                    f"{role}{i}" for i in range(1, int(quantity) + 1)
                ]
            except ValueError:
                pass

        for rq in role_distribution_options:
            rq_splitted = rq.split("=")
            if len(rq_splitted) != 2:
                self.elog(f"Role distribution '{rq}'is malformatted")
            hosts = None
            try:
                quantity = int(rq_splitted[1])
                hosts = [f"{rq_splitted[0]}{i}" for i in range(1, quantity + 1)]
            except ValueError:
                hosts = rq_splitted[1].split(",")

            roles_distribution[rq_splitted[0]] = hosts
        self.roles_distribution = roles_distribution


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
            except Exception as e:
                obj.handle_error(e)

        return update_wrapper(new_func, f)

    return decorator


class DeprecatedCmdDecorator(object):
    """This is a decorator which can be used to mark cmd as deprecated. It will
    result in a warning being emmitted when the command is invoked."""

    def __init__(self, message=""):
        if message:
            self.message = "%s." % message
        else:
            self.message = message

    def __call__(self, f):
        @click.pass_context
        def new_func(ctx, *args, **kwargs):
            msg = click.style(
                "warning: `%s` command is deprecated. %s"
                % (ctx.info_name, self.message),
                fg="yellow",
            )
            click.echo(msg)
            return ctx.invoke(f, *args, **kwargs)

        return update_wrapper(new_func, f)


class OnStartedDecorator(object):
    def __init__(self, callback):
        self.callback = callback
        self.exec_before = True

    def invoke_callback(self, ctx):
        if isinstance(self.callback, str):
            cmd = ctx.parent.command.get_command(ctx, self.callback)
            ctx.invoke(cmd)
        else:
            self.callback(ctx.obj)

    def __call__(self, f):
        @click.pass_context
        def new_func(ctx, *args, **kwargs):
            try:
                if self.exec_before:
                    self.invoke_callback(ctx)
                return ctx.invoke(f, *args, **kwargs)
            finally:
                if not self.exec_before:
                    self.invoke_callback(ctx)

        return update_wrapper(new_func, f)


class OnFinishedDecorator(OnStartedDecorator):
    def __init__(self, callback):
        super(on_finished, self).__init__(callback)
        self.exec_before = False


pass_context = make_pass_decorator(ensure=True)
on_started = OnStartedDecorator
on_finished = OnFinishedDecorator
