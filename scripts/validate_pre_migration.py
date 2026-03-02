"""Pre-migration validation for the v1.1.0 schema update.

Checks the production (or staging) database for data conditions that would
block or conflict with the planned constraint changes:

1. prize_draw_results rows with NULL ownership_id (must be backfilled or removed
   before the column can be made NOT NULL).
2. Duplicate (ownership_id, draw_type_id) pairs in prize_draw_results (would
   violate the new unique constraint).
3. Duplicate unique_nft_id values in user_nft_ownership (would violate the new
   unique index).
4. Duplicate non-null blockchain_nft_id values in user_nft_ownership (would
   violate the new partial unique index).
5. Orphaned prize_draw_results.ownership_id references (FK integrity check).
6. NULL ownership_id rows that cannot be resolved via (nft_id, user_id).

Usage:
    # Set DB_URL env var or accept the default from nictbw.db.engine
    python scripts/validate_pre_migration.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from nictbw.db.engine import make_engine


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

CHECKS: list[dict] = [
    {
        "name": "prize_draw_results with NULL ownership_id",
        "description": (
            "Rows that need backfill before ownership_id can become NOT NULL"
        ),
        "detail_query": text(
            "SELECT id, nft_id, draw_type_id, user_id "
            "FROM prize_draw_results "
            "WHERE ownership_id IS NULL "
            "ORDER BY id"
        ),
        "count_query": text(
            "SELECT count(*) FROM prize_draw_results WHERE ownership_id IS NULL"
        ),
        "blocking": True,
    },
    {
        "name": "Unresolvable NULL ownership_id rows via (nft_id, user_id)",
        "description": (
            "Rows where ownership_id is NULL and there is no matching "
            "user_nft_ownership row by (nft_id, user_id)"
        ),
        "detail_query": text(
            "SELECT pdr.id, pdr.nft_id, pdr.user_id, pdr.draw_type_id "
            "FROM prize_draw_results pdr "
            "LEFT JOIN user_nft_ownership uno "
            "  ON uno.nft_id = pdr.nft_id AND uno.user_id = pdr.user_id "
            "WHERE pdr.ownership_id IS NULL "
            "  AND uno.id IS NULL "
            "ORDER BY pdr.id"
        ),
        "count_query": text(
            "SELECT count(*) "
            "FROM prize_draw_results pdr "
            "LEFT JOIN user_nft_ownership uno "
            "  ON uno.nft_id = pdr.nft_id AND uno.user_id = pdr.user_id "
            "WHERE pdr.ownership_id IS NULL "
            "  AND uno.id IS NULL"
        ),
        "blocking": True,
    },
    {
        "name": "Duplicate (ownership_id, draw_type_id) in prize_draw_results",
        "description": (
            "Pairs that would violate the new "
            "uq_prize_draw_result_instance constraint"
        ),
        "detail_query": text(
            "SELECT ownership_id, draw_type_id, count(*) AS cnt "
            "FROM prize_draw_results "
            "WHERE ownership_id IS NOT NULL "
            "GROUP BY ownership_id, draw_type_id "
            "HAVING count(*) > 1 "
            "ORDER BY cnt DESC"
        ),
        "count_query": text(
            "SELECT count(*) FROM ("
            "  SELECT ownership_id, draw_type_id "
            "  FROM prize_draw_results "
            "  WHERE ownership_id IS NOT NULL "
            "  GROUP BY ownership_id, draw_type_id "
            "  HAVING count(*) > 1"
            ") sub"
        ),
        "blocking": True,
    },
    {
        "name": "Duplicate unique_nft_id in user_nft_ownership",
        "description": (
            "Values that would violate the new "
            "uq_nft_instance_unique_id unique index"
        ),
        "detail_query": text(
            "SELECT unique_nft_id, count(*) AS cnt "
            "FROM user_nft_ownership "
            "GROUP BY unique_nft_id "
            "HAVING count(*) > 1 "
            "ORDER BY cnt DESC"
        ),
        "count_query": text(
            "SELECT count(*) FROM ("
            "  SELECT unique_nft_id "
            "  FROM user_nft_ownership "
            "  GROUP BY unique_nft_id "
            "  HAVING count(*) > 1"
            ") sub"
        ),
        "blocking": True,
    },
    {
        "name": "Duplicate non-null blockchain_nft_id in user_nft_ownership",
        "description": (
            "Values that would violate the new partial unique index "
            "on blockchain_nft_id"
        ),
        "detail_query": text(
            "SELECT blockchain_nft_id, count(*) AS cnt "
            "FROM user_nft_ownership "
            "WHERE blockchain_nft_id IS NOT NULL "
            "GROUP BY blockchain_nft_id "
            "HAVING count(*) > 1 "
            "ORDER BY cnt DESC"
        ),
        "count_query": text(
            "SELECT count(*) FROM ("
            "  SELECT blockchain_nft_id "
            "  FROM user_nft_ownership "
            "  WHERE blockchain_nft_id IS NOT NULL "
            "  GROUP BY blockchain_nft_id "
            "  HAVING count(*) > 1"
            ") sub"
        ),
        "blocking": True,
    },
    {
        "name": "Orphaned prize_draw_results.ownership_id references",
        "description": (
            "Rows referencing a user_nft_ownership.id that does not exist"
        ),
        "detail_query": text(
            "SELECT pdr.id, pdr.ownership_id "
            "FROM prize_draw_results pdr "
            "LEFT JOIN user_nft_ownership uno ON pdr.ownership_id = uno.id "
            "WHERE pdr.ownership_id IS NOT NULL AND uno.id IS NULL "
            "ORDER BY pdr.id"
        ),
        "count_query": text(
            "SELECT count(*) "
            "FROM prize_draw_results pdr "
            "LEFT JOIN user_nft_ownership uno ON pdr.ownership_id = uno.id "
            "WHERE pdr.ownership_id IS NOT NULL AND uno.id IS NULL"
        ),
        "blocking": True,
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _row_to_str(row) -> str:
    """Format a result row for display."""
    return "  " + " | ".join(f"{k}={v}" for k, v in row._mapping.items())


def main() -> int:
    engine = make_engine()
    url_display = engine.url.render_as_string(hide_password=True)
    print(f"Pre-migration validation against: {url_display}\n")

    passed = 0
    failed = 0
    max_detail_rows = 20

    with engine.connect() as conn:
        for check in CHECKS:
            result = conn.execute(check["count_query"])
            count = result.scalar()

            if count == 0:
                print(f"  PASS  {check['name']}")
                passed += 1
            else:
                status = "FAIL" if check["blocking"] else "WARN"
                print(f"  {status}  {check['name']} — {count} issue(s) found")
                print(f"        {check['description']}")

                # Show detail rows
                detail_result = conn.execute(check["detail_query"])
                rows = detail_result.fetchmany(max_detail_rows + 1)
                for row in rows[:max_detail_rows]:
                    print(_row_to_str(row))
                if len(rows) > max_detail_rows:
                    print(f"  ... and more (showing first {max_detail_rows})")

                if check["blocking"]:
                    failed += 1
                print()

    print(f"\nSummary: {passed} passed, {failed} failed (blocking)")
    if failed > 0:
        print("Resolve all FAIL items before running the migration.")
        return 1
    print("All checks passed — safe to proceed with migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
