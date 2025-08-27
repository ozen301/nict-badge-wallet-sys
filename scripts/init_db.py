# File: scripts/init_db.py
from __future__ import annotations
import sys
from pathlib import Path

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from nictbw.db.engine import make_engine
from sqlalchemy import inspect
from nictbw.models import Base  # imports all model modules via __init__ side-effects


def main():
    engine = make_engine()
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    print("Created tables:", ", ".join(insp.get_table_names()))


if __name__ == "__main__":
    main()
