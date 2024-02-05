# Navigating the code

As we do not yet have a complete developper documentation, it is still useful to mention where the entry points of the software are. The `nxc` commands invoque `nixos_compose/cli.py` which in turns calls one of the files in `nixos_compose/commands` based on the _command verb_ it was provided. Here, _command verb_ is to be understood as a single word following the `nxc` characters after a space, like is done nowadays with several command line tools. For instance the _command verb_ for `nxc connect` is `connect`, which will be handled in `nixos_compose/commands/cmd_connect.py`.

You will find also that a `ctx` variable is extensively used. It refers to an instance of the `Context` object defined in `nixos_compose/context.py`.