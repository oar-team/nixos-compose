import yaml

class DefaultRole:
    def __init__(self, nb_min_nodes=0):
        self.nb_min_nodes = int(nb_min_nodes)

def default_role_constructor(loader, node):
    nb_min_nodes = loader.construct_scalar(node)
    return DefaultRole(nb_min_nodes)

def get_nxc_loader():
    loader = yaml.SafeLoader
    loader.add_constructor("!DefaultRole", default_role_constructor)
    return loader
