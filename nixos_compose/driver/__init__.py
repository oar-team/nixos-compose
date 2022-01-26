from pathlib import Path
import argparse
import ptpython.repl
import os
import time

from .logger import rootlog
from .driver import Driver


def generate_driver_symbols() -> None:
    """
    This generates a file with symbols of the test-driver code that can be used
    in user's test scripts. That list is then used by pyflakes to lint those
    scripts.
    """
    d = Driver([], [], "")
    test_symbols = d.test_symbols()
    with open("driver-symbols", "w") as fp:
        fp.write(",".join(test_symbols.keys()))
