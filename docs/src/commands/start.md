`nxc start [ROLE_DISTRIBUTION_FILE]`

Starts a set of nodes using the previous build. 

## Arguments

- `ROLE_DISTRIBUTION_FILE`
    positional argument in YAML format to describe how many instance of each role are expected.
    
    
## Example

- `nxc start`

   Start the last built composition.

- `nxc start nodes.yaml`

    With the file `nodes.yaml` written as this:

    ```yaml
    nfsServerNode: 1
    nfsClientNode: 2
    ```

    Instantiates two nodes with the role `nfsClientNode` and one only with the role `nfsServerNode`. Of course, these roles have to be described beforehand in a `composition.nix` file.

## Options

- `-f, --flavour` _flavourName_

    Choose the flavour to start.

- `-C, --composition-flavour [composition+flavour ... NAME]`

    Specifies which composition and flavour combination to start.

- `-I, --interactive`

    Drop into a python repl with driver functions

-  `-r, --role-distribution KEY=VALUE`

    Specify the number of nodes or nodes' name for a role (e.g. compute=2 or server=foo,bar ).

This the full list of options using `--help`.