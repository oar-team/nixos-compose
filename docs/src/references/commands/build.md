
`nxc build`

Builds the composition.

It generates a `build` folder which stores symlinks to the closure associated to a composition. The file name of the symlink follows this structure  `[composition-name]::[flavour]`

## Examples

- `nxc build -t vm`

    Build the `vm` flavor of your composition.

- `nxc build -C oar::g5k-nfs-store`

    Build the `oar` composition with the `g5k-nfs-store` flavor`.


## Usage

`nxc build [OPTIONS] [COMPOSITION_FILE]`

## Options

- `composition_file`


- `--nix-flags`
    add nix flags (aka options) to nix build command, --nix-flags "--impure"

- `--out-link, -o`
    path of the symlink to the build result

- `-f, --flavour`
    Use particular flavour (name or path)

- `-F, --list-flavours`
    List available flavour
    *Default:* `False`

- `--show-trace`
    Show Nix trace
    *Default:* `False`

- `--dry-run`
    Show what this command would do without doing it
    *Default:* `False`

- `--dry-build`
    Eval build expression and show store entry without building derivation
    *Default:* `False`

- `-C, --composition-flavour`
    Use to specify which composition and flavour combination to build when multiple compositions are describe at once (see -L options to list them).

- `-L, --list-compositions-flavours`
    List available combinations of compositions and flavours
    *Default:* `False`

- `-s, --setup`
    Select setup variant

- `-p, --setup-param`
    Override setup parameter

- `-u, --update-flake`
    Update flake.lock equivalent to: nix flake update
    *Default:* `False`

- `--monitor`
    Build with nix-output-monitor
    *Default:* `False`

- `--help`
    Show this message and exit.
    *Default:* `False`

