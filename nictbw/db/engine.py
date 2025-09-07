import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from typing import Optional

from .utils import resolve_sqlite_url

# Get DB_URL
load_dotenv()

# Resolve the DB_URL
# If DB_URL is not set, default to a local dev.db in the project root.
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = resolve_sqlite_url(
    os.getenv("DB_URL", "sqlite:///./dev.db"), ROOT_DIR
)


def make_engine(database_url: Optional[str] = None, echo: bool = False):
    """Create a SQLAlchemy engine using the configured database URL.

    Parameters
    ----------
    database_url : Optional[str]
        Database URL. Defaults to the value resolved from `DB_URL` env var
        or a local SQLite file.
    echo : bool
        Enable SQL logging for debugging. Defaults to ``False``.

    Returns
    -------
    Engine
        Configured SQLAlchemy engine instance.
    """
    url = database_url or DEFAULT_SQLITE_URL
    engine = create_engine(
        url,
        echo=echo,
    )
    return engine
