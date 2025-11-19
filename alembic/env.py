from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection, Engine
from dotenv import load_dotenv

# Ensure project root is on path and load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from nictbw.db.engine import DEFAULT_SQLITE_URL, make_engine
from nictbw.db.utils import resolve_sqlite_url
from nictbw.models import Base  # noqa: E402,F401 - import populates metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Provide SQLAlchemy metadata for autogeneration support.
target_metadata = Base.metadata


def _configured_database_url() -> str:
    env_url = os.getenv("DB_URL")
    if env_url:
        return resolve_sqlite_url(env_url, ROOT_DIR)
    return DEFAULT_SQLITE_URL


DATABASE_URL = _configured_database_url()

# Ensure Alembic always has a concrete URL to work with.
# Percent signs need to be escaped due to ConfigParser interpolation rules.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _engine() -> Engine:
    return make_engine(database_url=DATABASE_URL)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable: Engine | Connection = _engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=connection.engine.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
