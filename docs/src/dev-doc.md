# Developer Documentation

## Generate the CLI reference documentation

To generate the reference documentation directly from the code use this command:
```sh
python ./docs/tool/generate_md_doc.py dumps --baseModule=nixos_compose.cli --baseCommand=nxc --docsPath=./docs/src/references/commands
```