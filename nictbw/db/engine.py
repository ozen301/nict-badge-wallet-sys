from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .metadata import metadata_obj

import os
from pathlib import Path
from dotenv import load_dotenv
from .utils import resolve_sqlite_url

# Get DB url
load_dotenv()
# Project root directory (repo root)
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = resolve_sqlite_url(
    os.getenv("DB_URL", "sqlite:///./dev.db"), ROOT_DIR
)


from typing import Optional


def make_engine(database_url: Optional[str] = None, echo: bool = False):
    url = database_url or DEFAULT_SQLITE_URL
    # SQLite pragmas for better dev defaults
    engine = create_engine(
        url,
        echo=echo,
        future=True,
    )
    # if url.startswith("sqlite"):
    #     # ensure FK constraints are enforced on SQLite
    #     from sqlalchemy import event

    #     @event.listens_for(engine, "connect")
    #     def _set_sqlite_pragma(dbapi_connection, connection_record):
    #         cursor = dbapi_connection.cursor()
    #         cursor.execute("PRAGMA foreign_keys=ON")
    #         cursor.close()

    return engine


def get_sessionmaker(engine):
    return sessionmaker(
        bind=engine,
        # autoflush=False,
        expire_on_commit=False,  # Keep objects accessible after commit for dev convenience
        future=True,
    )
