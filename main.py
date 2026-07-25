"""
Hyperium entry point.

Delegates to the command line interface. Run `python main.py --help` for the
available commands.
"""

from interfaces.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
