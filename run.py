#!/usr/bin/env python3
"""Entry point: `python run.py --config config.yaml --once`."""

import sys

from monitor.cli import main

if __name__ == "__main__":
    sys.exit(main())
