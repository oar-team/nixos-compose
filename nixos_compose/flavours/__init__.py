"""
   nixos_compose.flavours
   Adapted from pygments project (pygments.styles)
   :copyright: Copyright 2006-2021 by the Pygments team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

#: Maps flavour names to 'submodule::classname'.
FLAVOUR_MAP = {
    "docker": "docker::DockerFlavour",
    "vm": "vm::VmFlavour",
    "vm-ramdisk": "vm::VmRamdiskFlavour",
    "g5k-nfs-store": "grid5000::G5kNfsStoreFlavour",
    "g5k-ramdisk": "grid5000::G5kRamdiskFlavour",
    "g5k-image": "grid5000::G5KImageFlavour",
}


class ClassNotFound(ValueError):
    """Raised if one of the lookup functions didn't find a matching class."""


def get_flavour_by_name(name):

    if name in FLAVOUR_MAP:
        mod, cls = FLAVOUR_MAP[name].split("::")

    try:
        mod = __import__("nixos_compose.flavours." + mod, None, None, [cls])
    except ImportError:
        raise ClassNotFound(f"Could not find flavour module {mod}")
    try:
        return getattr(mod, cls)
    except AttributeError:
        raise ClassNotFound(f"Could not find flavour class {cls} in flavour module.")


def use_flavour_method_if_any(f):
    def wrapper(*args, **kwargs):
        attr_name = f.__name__
        flavour = args[0].ctx.flavour
        if hasattr(flavour, attr_name):
            g = getattr(flavour, attr_name)
            # isinstance isn't use to avoid circular dependencies
            if args[0].__class__.__name__ == "Driver":
                args = args[1:]
            return g(*args, **kwargs)
        else:
            return f(*args, **kwargs)

    return wrapper
