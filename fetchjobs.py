#!/usr/bin/env python3
"""Create `.venv` if needed, then export jobs to Supabase."""

from src.bootstrap import bootstrap

if __name__ == "__main__":
    bootstrap()
    from src.export import main

    main()
