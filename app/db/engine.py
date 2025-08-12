from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .metadata import metadata_obj

DEFAULT_SQLITE_URL = "sqlite:///./dev.db"


def make_engine(database_url: str | None = None, echo: bool = False):
    url = database_url or DEFAULT_SQLITE_URL
    # SQLite pragmas for better dev defaults
    engine = create_engine(
        url,
        echo=echo,
        future=True,
    )
    if url.startswith("sqlite"):
        # ensure FK constraints are enforced on SQLite
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_sessionmaker(engine):
    return sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )
