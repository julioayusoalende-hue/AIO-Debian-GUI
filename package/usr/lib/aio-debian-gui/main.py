#!/usr/bin/python3
"""Entry point for AIO Debian GUI - modular version."""

import sys
import os

# Añadir el directorio lib al path
LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aio-debian-gui")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from ui import main

if __name__ == "__main__":
    main()