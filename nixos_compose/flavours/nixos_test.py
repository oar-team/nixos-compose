from ..flavour import Flavour
from ..actions import generate_deployment_info, ssh_connect


class NixosTestFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "nixos-test"


class NixosTestDriverFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "nixos-test-driver"


class NixosTestSshFlavour(Flavour):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.name = "nixos-test-ssh"

    def generate_deployment_info(self):
        generate_deployment_info(self.ctx)

    def ext_connect(self, user, node, execute=True):
        return ssh_connect(self.ctx, user, node, execute)
