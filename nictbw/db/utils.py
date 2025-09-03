from pathlib import Path


def resolve_sqlite_url(url: str, project_root: Path) -> str:
    """Resolve 'sqlite:///./relative/path' to an absolute sqlite:/// URL.

    Keeps other URL forms unchanged.
    """
    prefix = "sqlite:///./"
    if not url.startswith(prefix):
        return url
    rel = url[len(prefix) :]
    return f"sqlite:///{(project_root / rel).resolve()}"
