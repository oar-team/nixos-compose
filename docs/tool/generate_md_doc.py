#!/usr/bin/env python3

# DISCLAIMER:
# This code is freely adapted from https://github.com/RiveryIO/md-click
#
# LICENSE:
# BSD 3-Clause License
# 
# Copyright (c) 2021, Rivery
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import pathlib
import importlib
import itertools
import os

import click

# Edit this template to change markdown output
md_base_template = """
`{command_name}`

{description}

## Usage

`{usage}`

## Options

{options}
"""


def trim_trailing_spaces(data: str):
    """
    Trim trailing whitespaces from text.
    """
    return '\n'.join(line.rstrip() for line in data.splitlines())


def trim_empty_lines(data: str):
    """
    Remove empty lines from start and end of text.
    """
    def empty(x):
        return x == ""

    lines = data.splitlines()
    lines = list(itertools.dropwhile(empty, lines))
    lines = reversed(lines)
    lines = list(itertools.dropwhile(empty, lines))
    lines = reversed(lines)
    return '\n'.join(lines)


def trim_docstring(data):
    """
    Remove common indentation from documentation string.
    Example: "  Hello,\n   World!" -> "Hello,\n World!"
             Lines have common indentation of 2 spaces,
             which will be removed by this function.
    """
    lines = trim_empty_lines(data).splitlines()

    common_indentation = min([
        len(list(itertools.takewhile(
            lambda x: x == ' ' or x == '\t',
            line
        ))) for line in lines if line
    ])

    return '\n'.join([line[common_indentation:] for line in lines])


def recursive_help(cmd, parent=None):
    """
    Recursively get help options from command and it's children.
    """
    print(cmd)
    ctx = click.core.Context(cmd, info_name=cmd.name, parent=parent)
    try:
        commands = cmd.list_commands(ctx)
    except AttributeError:
        commands = []

    yield {
        "command": cmd,
        "help": cmd.get_help(ctx),
        "parent": parent.info_name if parent else '',
        "usage": cmd.get_usage(ctx),
        "params": cmd.get_params(ctx),
        "options": cmd.collect_usage_pieces(ctx),
        "commands": {sub_command_name: cmd.get_command(ctx, sub_command_name) for sub_command_name in commands}
    }
    
    for sub_command_name in commands:
        for helpdct in recursive_help(cmd.get_command(ctx, sub_command_name), ctx):
            yield helpdct


def format_option(opt):
    usage = ', '.join(opt.get('usage').splitlines())
    required = ' (REQUIRED)' if opt.get('required') else ''
    default_value = opt.get('default', None)

    # special case
    if default_value == os.getcwd():
        default_value = "<current directory>"

    res = f"- `{usage}`{required}\n    {opt.get('help') or ''}\n"

    if default_value is not None:
        res += f"    *Default:* `{default_value}`\n"

    res += "\n"

    return res


def shorten_help(help_message: str) -> str:
    # Get the first line with content
    for line in  help_message.split('\n'):
        if line:
            short_help = line.strip()
            break
    short_help = info = (short_help[:80] + '...') if len(short_help) > 80 else short_help
    return short_help



def dump_helper(base_command, docs_dir):
    """ Dumping help usage files from Click Help files into an md """
    docs_path = pathlib.Path(docs_dir)
    for helpdct in recursive_help(base_command):
        command = helpdct["command"]
        helptxt = helpdct["help"]
        usage = helpdct["usage"]

        options = {
            opt.name: {
                "usage": '\n'.join(opt.opts),
                "prompt": getattr(opt, "prompt", None),
                "required": getattr(opt, "required", None),
                "default": getattr(opt, "default", None),
                "help": getattr(opt, "help", None),
                "type": str(getattr(opt, "type", None))
            }
            for opt in helpdct.get('params', [])
        }

        if helpdct.get("parent"):
            command_name = helpdct["parent"] + " " + command.name
        else:
            command_name = command.name

        md_template = md_base_template.format(
            command_name=command_name,
            description=trim_docstring(command.help),
            usage=usage.removeprefix("Usage: "),
            options="".join([
                format_option(opt)
                for _, opt in options.items()
            ]),
            help=helptxt
        )
        if helpdct.get("commands"):
            commands = "\n".join([
                f"- `{cmd_name}`\n    {shorten_help(cmd_value.help)}" for cmd_name, cmd_value in helpdct["commands"].items()])
            md_template += """## Commands

{commands}
""".format(commands=commands)

        if not docs_path.exists():
            # Create md file dir if needed
            docs_path.mkdir(parents=True, exist_ok=False)

        md_file_path = docs_path.joinpath(command.name.replace(' ', '-').lower() + '.md').absolute()

        # Create the file per each command
        with open(md_file_path, 'w', encoding='utf-8') as md_file:
            md_file.write(trim_trailing_spaces(md_template))


@click.group()
def cli():
    pass


@cli.command('dumps')
@click.option('--baseModule', help='The base command module path to import', required=True)
@click.option('--baseCommand', help='The base command function to import', required=True)
@click.option('--docsPath', help='The docs dir path to write the md files', required=True)
def dumps(**kwargs):
    """
    # Click-md
    Create md files per each command,
    in format of `command.md`,
    under the `--docsPath` directory.
    """
    base_module = kwargs.get('basemodule')
    base_command = kwargs.get('basecommand')
    docs_path = kwargs.get('docspath')

    click.secho(f'Creating a new documents from {base_module}.{base_command} into {docs_path}',
                color='green')

    try:
        # Import the module
        module_ = importlib.import_module(base_module)
    except Exception as e:
        click.echo(f'Could not find module: {base_module}. Error: {str(e)}')
        return

    try:
        # Import the base command (group of command) function inside the module
        command_ = getattr(module_, base_command)
    except AttributeError:
        click.echo(f'Could not find command {base_command} on module {base_module}')
        return

    try:
        dump_helper(command_, docs_dir=docs_path)
        click.secho(f'Created docs under {docs_path}', color='green')
    except Exception as e:
        click.secho(f'Dumps command failed: {str(e)}', color='red')
        raise

    return


cli.add_command(cli)
cli()
