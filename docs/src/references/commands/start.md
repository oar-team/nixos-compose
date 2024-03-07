
`nxc start`

Starts a set of nodes using the previous build.

`ROLE_DISTRIBUTION_FILE` is and optional YAML file describing how many instance of each role are expected.

## Examples

- `nxc start`

   Start the last built composition.

- `nxc start role-distrib.yaml`

    With the file `role-distrib.yaml` written as this:

    ```yaml
    nfsServerNode: 1
    nfsClientNode: 2
    ```

    Instantiates two nodes with the role `nfsClientNode` and one only with the role `nfsServerNode`. Of course, these roles have to be described beforehand in a `composition.nix` file.



## Usage

`nxc start [OPTIONS] [ROLES_DISTRIBUTION_FILE]`

## Options

- `-I, --interactive`
    drop into a python repl with driver functions
    *Default:* `False`

- `-m, --machine-file`
    file that contains remote machines names to (duplicates are considered as one).

- `-W, --wait-machine-file`
    wait machine-file creation
    *Default:* `False`

- `-s, --ssh`
    specify particular ssh command
    *Default:* `ssh -l root `

- `-S, --sudo`
    specify particular sudo command
    *Default:* `sudo`

- `--push-path`
    remote path where to push image, kernel and kexec_script on machines (use to re-kexec)

- `--reuse`
    supposed a previous succeded start (w/ root access via ssh)
    *Default:* `False`

- `--remote-deployment-info`
    deployement info is served by http (in place of kernel parameters)
    *Default:* `False`

- `--port`
    Port to use for the HTTP server
    *Default:* `0`

- `-c, -C, --composition`
    specify composition, can specify flavour e.g. composition::flavour

- `-f, --flavour`
    specify flavour

- `-t, --test-script`
    execute testscript
    *Default:* `False`

- `--file-test-script`
    alternative testscript

- `-w, --sigwait`
    wait any signal to exit after a start only action (not testscript execution or interactive use
    *Default:* `False`

- `-k, --kernel-params`
    additional kernel parameters, this option is flavour dependent

- `-r, --role-distribution`
    specify the number of nodes or nodes' name for a role (e.g. compute=2 or server=foo,bar ).

- `roles_distribution_file`


- `--compose-info`
    specific compose info file

- `-i, --identity-file`
    path to the ssh public key to use to connect to the deployments

- `-s, --setup`
    Select setup variant

- `-p, --parameter`
    Parameter added to deployment file (for contextualization phase)

- `-P, --parameter-file`
    Json file contains parameters added to deployment file (for contextualization phase)

- `-d, --deployment-file`
    Deployement json file use for the deployment (skip generation) Warning parametrization not supported (upto now)

- `--ip-range`
    IP range (for now only usable with nspawn flavour)
    *Default:* ``

- `--help`
    Show this message and exit.
    *Default:* `False`

