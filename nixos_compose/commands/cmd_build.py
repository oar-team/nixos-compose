
import click

from ..context import pass_context

import time
import sys
import subprocess

@click.command('build')

@pass_context
@click.argument('composition_file', type=click.STRING)
@click.option('--nix-path', '-I', multiple=True, help='add a path to the list of locations used to look up <...> file names')
@click.option('--out-link', '-o',default='result', help='path of the symlink to the build result')
@click.option('--nixpkgs', '-n', default="channel:nixos-20.09")
@click.option('--nixos-test', is_flag=True, help='generate NixOS Test driver') 
#  nix build -f examples/webserver-flavour.nix -I compose=nix/compose.nix -I nixpkgs=channel:nixos-20.09 -o result-local

def cli(ctx, composition_file, nix_path, out_link, nixpkgs, nixos_test):
    """Build multi Nixos composition."""
    ctx.log('Starting build')
    
    build_cmd = f"nix build -f {composition_file} -I  compose=nix/compose.nix "
    build_cmd += f"-I nixpkgs={nixpkgs} -o {out_link}"
    if nixos_test:
        build_cmd += ' driver'
    
    ctx.vlog(build_cmd)
    subprocess.call(build_cmd, shell=True)
    ctx.glog('Build completed')
    
