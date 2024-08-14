
`nxc driver`

Run the driver to execute the given script to interact with the deployed environment.
The script is a python script similar to nixos-test script. See the [NixOS manual on nixos-tests](https://nixos.org/manual/nixos/unstable/#sec-writing-nixos-tests) for more details.

```admonish warning
Be aware that unlike Nixos-test that only support virtual machines, `nxc` supports many flavours and VM specific features are not supported.
```

## Examples

- `nxc driver -t`

   Run the script defined in the composition


## Usage

`nxc driver [OPTIONS] [TEST_SCRIPT_FILE]`

## Options

- `-l, --user`

    *Default:* `root`

- `-d, --deployment-file`
    Deployment file, take the latest created in deploy directory by default

- `-f, --flavour`
    flavour, by default it's extracted from deployment file name

- `-t, --test-script`
    execute the 'embedded' testScript
    *Default:* `False`

- `test-script-file`


- `--help`
    Show this message and exit.
    *Default:* `False`

