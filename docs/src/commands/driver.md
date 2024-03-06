`nxc driver [TEST_SCRIPT_FILE]`

Run the driver to execute the given script to interact with the deployed environment.
The script is a python nixos-test script. See the [NixOS manual on nixos-tests](https://nixos.org/manual/nixos/unstable/#sec-writing-nixos-tests) for more details.

```admonish warning
Be aware that unlike Nixos-test that only support virtual machines, `nxc` supports many flavors and VM specific features are not supported. 
```

## Examples

- `nxc driver -t`
  Run the script defined in the composition

## Options

- `-t`, `--test-script`
   execute the 'embedded' testscript defined in the composition
