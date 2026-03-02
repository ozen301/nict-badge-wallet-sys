"""Deduplicate unique_nft_id values in user_nft_ownership.

Under the old schema, different users' instances of the same NFT definition
could share the same ``unique_nft_id`` (provided by blockchain sync).  The
v1.1.0 migration adds a unique index on this column, so duplicates must be
resolved first.

Strategy: for each group of duplicates, keep the row with the lowest ``id``
unchanged and suffix the others with ``-u{user_id}`` to make them unique while
remaining traceable.  If that still collides, append ``-r{row_id}`` instead.

Usage:
    # Dry-run  (default) — report what would change, touch nothing
    python scripts/dedup_unique_nft_id.py

    # Apply changes
    python scripts/dedup_unique_nft_id.py --apply
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from nictbw.db.engine import make_engine


def main() -> int:
    apply = "--apply" in sys.argv
    engine = make_engine()
    url_display = engine.url.render_as_string(hide_password=True)
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] Dedup unique_nft_id against: {url_display}\n")

    # ------------------------------------------------------------------ #
    # Gather duplicates                                                   #
    # ------------------------------------------------------------------ #
    with engine.connect() as conn:
        dup_groups = conn.execute(text(
            "SELECT unique_nft_id, array_agg(id ORDER BY id) AS ids, "
            "       array_agg(user_id ORDER BY id) AS user_ids "
            "FROM user_nft_ownership "
            "GROUP BY unique_nft_id "
            "HAVING count(*) > 1 "
            "ORDER BY unique_nft_id"
        )).fetchall()

        if not dup_groups:
            print("No duplicates found — nothing to do.")
            return 0

        # Collect all existing unique_nft_id values for collision checking
        all_existing = set(
            row[0] for row in conn.execute(text(
                "SELECT unique_nft_id FROM user_nft_ownership"
            )).fetchall()
        )

        total_groups = len(dup_groups)
        total_rows_to_fix = sum(len(row.ids) - 1 for row in dup_groups)
        print(f"Found {total_groups} duplicate groups, {total_rows_to_fix} rows to fix.\n")

        updates: list[tuple[int, str, str]] = []  # (row_id, old_value, new_value)

        for row in dup_groups:
            old_uid = row.unique_nft_id
            ids = row.ids
            user_ids = row.user_ids

            # Keep the first row (lowest id) as-is
            keeper_id = ids[0]
            for row_id, user_id in zip(ids[1:], user_ids[1:]):
                # Try suffix with user_id first
                candidate = f"{old_uid}-u{user_id}"[:255]
                if candidate not in all_existing and candidate not in {u[2] for u in updates}:
                    new_uid = candidate
                else:
                    # Fall back to row-id suffix
                    new_uid = f"{old_uid}-r{row_id}"[:255]

                updates.append((row_id, old_uid, new_uid))
                print(f"  id={row_id:>6d}  {old_uid}  →  {new_uid}")

        print(f"\nTotal updates: {len(updates)}")

        if not apply:
            print("\nRe-run with --apply to execute these changes.")
            return 0

    # -------------------------------------------------------------------- #
    # Apply updates                                                         #
    # -------------------------------------------------------------------- #
    with engine.begin() as conn:
        for row_id, _, new_uid in updates:
            conn.execute(
                text(
                    "UPDATE user_nft_ownership "
                    "SET unique_nft_id = :new_uid "
                    "WHERE id = :row_id"
                ),
                {"new_uid": new_uid, "row_id": row_id},
            )
    print(f"\nSuccessfully updated {len(updates)} rows.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
