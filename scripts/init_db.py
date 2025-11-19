from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from nictbw.db.engine import make_engine


def upgrade_db(target_revision: str = "head") -> None:
    """Apply Alembic migrations up to the requested revision."""
    project_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    command.upgrade(alembic_cfg, target_revision)


def print_tables() -> None:
    """Inspect the configured database and print all table names."""
    engine = make_engine()
    insp = inspect(engine)
    print("Current tables:", ", ".join(sorted(insp.get_table_names())))


def main() -> None:
    """Apply migrations (default to head) and report the resulting schema."""
    upgrade_db()
    print_tables()


if __name__ == "__main__":
    main()
