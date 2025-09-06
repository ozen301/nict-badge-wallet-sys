import unittest
import tempfile
from pathlib import Path

from nictbw.db.utils import resolve_sqlite_url


class TestResolveSqliteUrl(unittest.TestCase):
    def test_non_sqlite_prefix_unchanged(self):
        url = "postgresql+psycopg://user:pass@localhost/db"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            self.assertEqual(resolve_sqlite_url(url, project_root), url)

    def test_relative_to_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            relative_url = "sqlite:///./dev.db"
            resolved = resolve_sqlite_url(relative_url, project_root)
            self.assertTrue(resolved.startswith("sqlite:///"))
            abs_path = resolved[len("sqlite:///"):]
            self.assertEqual(Path(abs_path), (project_root / "dev.db").resolve())


if __name__ == "__main__":
    unittest.main()
