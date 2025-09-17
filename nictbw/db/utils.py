from pathlib import Path
from datetime import datetime
from typing import Optional


def resolve_sqlite_url(url: str, project_root: Path) -> str:
    """Resolve 'sqlite:///./relative/path' to an absolute sqlite:/// URL.

    Keeps other URL forms unchanged.
    """
    prefix = "sqlite:///./"
    if not url.startswith(prefix):
        return url
    rel = url[len(prefix) :]
    return f"sqlite:///{(project_root / rel).resolve()}"


def dt_iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to an ISO 8601 string in UTC, or return None.

    This is a small helper intended for serializing timestamps in JSON.
    """
    from datetime import timezone

    if dt is None:
        return None
    try:
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return getattr(dt, "isoformat", lambda: None)()
