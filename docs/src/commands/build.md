`nxc build` builds the composition. Generates a `build` folder which stores symlinks to the closure associated to a composition. The file name of the symlink follows this struture :

```
[[composition-name]]::[flavour]

soon ??
[[composition-name]::[system]]::[flavour]

```
## The is non requiered argument *composition_file* to remove i think
# Options

- `-f, --flavour` _flavourName_

    Choose the flavour to build the composition.

- `-F, --list-flavours`

    Displays the list of flavours.

- `--show-trace`

    Show Nix Trace in case of build error.

- `--dry-run`

    Show what this command would do without doing it.

- `--dry-build`

    Eval build expression and show store entry without building derivation.

- `-C, --composition-flavour [composition+flavour ... NAME]`

    Use to specify which composition and flavour combinaison to built when muliple compostions are describe at once (see -L options to list them).

- `-L, --list-composition-flavours`

    List available combinaisons of compositions and flavours.

- `-s, --setup`

    Select setup variant

- `-p, --setup-param`

    Override setup parameter

- `-o, --out-link`

    Path of the symlink to the build result.
