from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from nictbw.db.engine import make_engine


def print_tables() -> None:
    """Inspect the configured database and print all table names."""
    engine = make_engine()
    insp = inspect(engine)
    print("Current tables:", ", ".join(sorted(insp.get_table_names())))


def main() -> None:
    """Apply Alembic migrations and report the resulting schema."""
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    command.upgrade(alembic_cfg, "head")
    print_tables()


if __name__ == "__main__":
    main()
