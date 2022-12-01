import click
import sys
from ..context import pass_context
from ..g5k import key_sleep_script
from ..actions import install_nix_static, get_ip_ssh_port


def print_helper(ctx, options):
    option = options[0]
    if (option == "g5k_script") or (option == "g5k-script"):
        click.echo(key_sleep_script)
    elif option == "install-nix":
        install_nix_static(ctx)
    elif option == "ip":
        if len(options) > 1:
            ip, _ = get_ip_ssh_port(ctx, options[1])
            print(f"{ip}")
        else:
            ctx.elog("Host argument required")
            sys.exit(1)
    elif option == "ip_ssh_port":
        if len(options) > 1:
            ip, ssh_port = get_ip_ssh_port(ctx, options[1])
            print(f"{ip}:{ssh_port}")
        else:
            ctx.elog("Host argument required")
            sys.exit(1)
    else:
        ctx.elog(f"Helper: {option} does not exist")
        sys.exit(1)


def print_helper_list(helper_options):
    print("g5k-script: print path to g5k_key_sleep_script Grid'5000 script")
    print("install-nix: install the nix command in ~/.local/bin")
    print("ip <composition_hostname>: print hostname's ip address")
    print(
        "ip_ssh_port <composition_hostname>: print hostname's ip address and ssh port"
    )


@click.command("helper")
@click.option(
    "-l",
    "--list",
    # "--list-helpers",
    is_flag=True,
    help="List of available helpers",
)
@pass_context
@click.argument("options", nargs=-1)
def cli(ctx, options, list):
    """Specific and contextual helper information (e.g. g5k_script path for Grid'5000)
    Warning: Experimental command, may be removed in the future or change without backward compatibility care."""

    if options:
        print_helper(ctx, options)

    if list:
        print_helper_list(ctx)
