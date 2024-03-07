
`nxc init`

Initialize a new environment.

## Usage

`nxc init [OPTIONS]`

## Options

- `--no-symlink`
    Disable symlink creation to nxc.json (need to change directory for next command
    *Default:* `False`

- `-n, --disable-detection`
    Disable platform detection.
    *Default:* `False`

- `-f, --default-flavour`
    Set default flavour to build, if not given nixos-compose try to find a good

- `--list-flavours-json`
    List description of flavours, in json format
    *Default:* `False`

- `-F, --list-flavours`
    List available flavour
    *Default:* `False`

- `-t, --template`
    Use a template
    *Default:* `basic`

- `--use-local-templates`
    Either use the local templates or not
    *Default:* `False`

- `--list-templates-json`
    Display the list of available templates as JSON
    *Default:* `False`

- `--help`
    Show this message and exit.
    *Default:* `False`

