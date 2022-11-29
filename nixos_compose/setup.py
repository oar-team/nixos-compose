import os
import os.path as op
import tomlkit


def apply_setup(
    ctx,
    selected_setup,
    nix_flags,
    composition_file,
    composition_flavour,
    flavour,
    setup_param,
    kernel_params,
    filename="setup.toml",
):

    update_setup_file = False

    setup_file = op.join(ctx.envdir, filename)
    if not op.exists(setup_file):
        return (nix_flags, composition_file)

    setup_toml = tomlkit.loads(open(op.join(ctx.envdir, setup_file)).read())

    if (
        not selected_setup
        and "project" in setup_toml
        and "selected" in setup_toml["project"]
    ):
        ctx.wlog(
            "Detecting selected setup variant without asking it, removing it from setup file "
        )
        del setup_toml["project"]["selected"]
        update_setup_file = True

    # Handle setup parameters
    # First remove if any
    if "override-params" in setup_toml:
        del setup_toml["override-params"]
    # Second set override parmetes is needed
    if setup_param:
        override_params = tomlkit.table()
        setup_toml["override-params"] = override_params
        for param in setup_param:
            n, v = param.split("=")
            try:
                v = int(v)
            except ValueError:
                pass
            override_params.add(n, v)
        update_setup_file = True

    if update_setup_file:
        with open(setup_file, "w") as f:
            f.write(tomlkit.dumps(setup_toml))
            f.flush()
            os.fsync(f.fileno())

    if "options" in setup_toml:
        if not nix_flags and "nix-flags" in setup_toml["options"]:
            nix_flags = setup_toml["options"]["nix-flags"]
        if not composition_file and "composition-file" in setup_toml["options"]:
            composition_file = setup_toml["options"]["composition-file"]
        if not composition_flavour and "composition-flavour" in setup_toml["options"]:
            composition_flavour = setup_toml["options"]["composition-flavour"]
        if not flavour and "flavour" in setup_toml["options"]:
            flavour = setup_toml["options"]["flavour"]
        if not kernel_params and "kernel-params" in setup_toml["options"]:
            kernel_params = setup_toml["options"]["kernel-params"]

    if selected_setup:
        if selected_setup not in setup_toml:
            ctx.elog("Missing asked setup variant: ${selected_setup}")
            sys.exit(1)
        else:
            if "options" in setup_toml[selected_setup]:
                if "nix-flags" in setup_toml[selected_setup]["options"]:
                    nix_flags = setup_toml[selected_setup]["options"]["nix-flags"]

                if "composition-file" in setup_toml[selected_setup]["options"]:
                    composition_file = setup_toml[selected_setup]["options"][
                        "composition-file"
                    ]
                if "kernel-params" in setup_toml[selected_setup]["options"]:
                    kernel_params = setup_toml[selected_setup]["options"][
                        "kernel-params"
                    ]

            if "project" not in setup_toml:
                project = tomlkit.table()
                setup_toml.add("selected", selected_setup)
            else:
                setup_toml["project"]["selected"] = selected_setup

            with open(setup_file, "w") as f:
                f.write(tomlkit.dumps(setup_toml))
                f.flush()
                os.fsync(f.fileno())

    ctx.setup = setup_toml

    return (nix_flags, composition_file, composition_flavour, flavour, kernel_params)
