# -*- coding: utf-8 -*-
"""Entry point of the packaged (PyInstaller) standalone app: same as `python -m standalone`."""
import sys

from standalone.main import main

if __name__ == "__main__":
    sys.exit(main())
