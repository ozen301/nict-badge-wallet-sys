from __future__ import annotations

import sys

from alembic.autogenerate import api as ag_api
from alembic.runtime.migration import MigrationContext

from nictbw.db.engine import make_engine
from nictbw.models import Base


def _print_ops(ops, indent: int = 0) -> None:
    prefix = "  " * indent
    for op in ops:
        print(f"{prefix}- {op}")
        sub_ops = getattr(op, "ops", None)
        if sub_ops:
            _print_ops(sub_ops, indent + 1)


def main() -> int:
    engine = make_engine()
    url_display = engine.url.render_as_string(hide_password=True)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection=connection,
                opts={
                    "compare_type": True,
                    "compare_server_default": True,
                    "render_as_batch": connection.dialect.name == "sqlite",
                },
            )
            migration = ag_api.produce_migrations(context, Base.metadata)
            upgrade_ops = migration.upgrade_ops
            if upgrade_ops is None:
                print(f"Schema drift check: ERROR for {url_display}: missing upgrade ops.")
                return 2
            if upgrade_ops.is_empty():
                print(f"Schema drift check: OK (no differences) for {url_display}.")
                return 0
            print(f"Schema drift check: FAILED for {url_display}. Differences detected:")
            _print_ops(upgrade_ops.ops or [])
            return 1
    except Exception as exc:
        print(f"Schema drift check: ERROR for {url_display}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
