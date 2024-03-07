
`nxc`

Generate and manage Nixos-compositions.

## Usage

`nxc [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...`

## Options

- `--envdir, -d`
    Changes the folder to operate on.
    *Default:* `/home/mmercier/Projects/nixos-compose/nxc`

- `--verbose, -v`
    Verbose mode.
    *Default:* `False`

- `--debug, -D`
    Enable debugging
    *Default:* `False`

- `--version`
    Show the version and exit.
    *Default:* `False`

- `--help`
    Show this message and exit.
    *Default:* `False`


## Commands

- `build`
    Builds the composition.
- `clean`
    Clean the nxc folder and nxc.json file
- `connect`
    Opens one or more terminal sessions into the deployed nodes. By default, it will...
- `driver`
    Run the driver to execute the given script to interact with the deployed environ...
- `helper`
    Specific and contextual helper information (e.g. g5k_script path for Grid'5000)
- `init`
    Initialize a new environment.
- `start`
    Starts a set of nodes using the previous build.
- `stop`
    Stop Nixos composition.