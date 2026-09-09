#!/usr/bin/env python3
"""Create `.venv` if needed, then run the job monitor."""

from src.bootstrap import bootstrap

if __name__ == "__main__":
    bootstrap()
    from src.cli import main

    main()
