from ..flavour import Flavour


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
