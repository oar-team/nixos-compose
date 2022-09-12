import json
import os.path as op
import pprint

from io import open
from .utils import touch


# TOREMOVE
class State(dict):
    DEFAULTS = {"built": False, "started": False}

    def __init__(self, ctx, state_file):
        dict.__init__(self, self.DEFAULTS)
        self.ctx = ctx
        self.state_file = state_file
        self.load()

    def load(self):
        if op.isfile(self.state_file):
            try:
                with open(self.state_file, "rt") as json_file:
                    self.update(json.loads(json_file.read()))
            except Exception:
                pass

    def dump(self):
        if op.isdir(self.ctx.envdir):
            touch(self.state_file)
            if op.isdir(op.dirname(self.state_file)):
                with open(self.state_file, "w", encoding="utf8") as json_file:
                    json_file.write(json.dumps(self, ensure_ascii=False))

    def __str__(self):
        return pprint.pprint(self)
