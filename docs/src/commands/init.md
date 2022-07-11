`nxc init` helps you starts a new project by creating the firsts required files.

# Examples

## Initilisation

`nxc init -t basic --output-dir experiments`
This command fetches on the git repository on _NixOS Compose_ 
`nxc init -

TODO continue

# Options

`--output-dir [path]`
Defines where to initialize. default value is the current directory

`-t, --templates [template]`
Copies the files of the corresponding template.

`-f, --default-flavour [flavour]`
Defines the default flavour to build when no flavour are specified for the build command.

`-F, --list-flavours`
Displays the list of available flavours.

`--no-flake-lock`
Do not imports a pre-generated `flake.lock` file. Templates are tested on this lock file.

`--list-flavours-json`
List of flavours in the JSON format.

`--list-templates`
Displays the list of the available templates

`--list-templates-json`
List of templates in the JSON format