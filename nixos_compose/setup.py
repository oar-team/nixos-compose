import os
import os.path as op
import tomlkit 

def apply_setup(ctx, selected_setup, nix_flags, composition_file, filename="setup.toml"):
    
    setup_file = op.join(ctx.envdir, filename)
    if not op.exists(setup_file):
        return(nix_flags, composition_file)
    
    setup_toml = tomlkit.loads(open(op.join(ctx.envdir, setup_file)).read())

    if not selected_setup and 'project' in setup_toml and 'selected' in setup_toml['project']:
        ctx.wlog("Detecting selected setup variant without asking it, removing it from setup file ")
        del setup_toml['project']['selected']
        
        with open(setup_file, 'w') as f:
                    f.write(tomlkit.dumps(setup_toml))
                    f.flush()
                    os.fsync(f.fileno())
                    
    if 'options' in setup_toml:
        if 'nix-flags' in setup_toml['options']:
            nix_flags = setup_toml['options']['nix-flags']    
        if 'composition-file' in setup_toml['options']:
            composition_file = setup_toml['options']['composition-file']

    if selected_setup:
        if selected_setup not in setup_toml:
            ctx.elog("Missing asked setup variant: ${selected_setup}")
            sys.exit(1)
        else:
            if 'options' in setup_toml[selected_setup]:
                if 'nix-flags' in setup_toml[selected_setup]['options']:
                    nix_flags = setup_toml[selected_setup]['options']['nix-flags']
                    
                if 'composition-file' in setup_toml[selected_setup]['options']:
                    composition_file = setup_toml[selected_setup]['options']['composition-file']

            if 'project' not in setup_toml:
                project = table()
                setup_toml.add('selected', selected_setup)
            else:
                setup_toml['project']['selected'] = selected_setup
                
            with open(setup_file, 'w') as f:
                    f.write(tomlkit.dumps(setup_toml))
                    f.flush()
                    os.fsync(f.fileno())

    ctx.setup = setup_toml
        
    return(nix_flags, composition_file)
