"""
CLI wrapper for app/services/data_loader.py -- see that module for the
actual loading logic and design notes (it lives under app/ rather than
scripts/ so it also ships with the deployed Vercel function; see
app/api/admin.py's bootstrap endpoint).

Usage:
    python scripts/load_data.py [--reset]

--reset truncates all tables first, so the script is safe to re-run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import engine  # noqa: E402
from app.services.data_loader import load_all  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Truncate all tables before loading")
    args = parser.parse_args()
    load_all(engine, reset=args.reset)
