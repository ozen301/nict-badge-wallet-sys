# Schema Follow-Up Memo (Post-Refactor)

Date: 2026-02-27  
Context: Python API semantics are now instance-first, while the DB schema still reflects legacy naming and uniqueness assumptions.

## Why This Memo Exists
The current code now treats:
- `nfts` rows as NFT definitions (`NFTDefinition`)
- `user_nft_ownership` rows as NFT instances (`NFTInstance`)
- prize draw evaluations as instance-based (`ownership_id` is primary)

However, the DB still enforces old constraints, so some correct instance-level operations are blocked or forced to hard-fail.

## Must-Do Schema Changes

1. `prize_draw_results` uniqueness must be instance-based
- Current: unique on `(nft_id, draw_type_id)`
- Target: unique on `(ownership_id, draw_type_id)`
- Reason: one definition can have multiple instances; each instance needs an independent draw result.

2. `user_nft_ownership` uniqueness must allow multiple instances per user per definition
- Current: unique on `(user_id, nft_id)`
- Target: remove this unique constraint.
- Add/confirm uniqueness for true instance identity fields:
  - `unique_nft_id` should be unique.
  - `blockchain_nft_id` should be unique when present (partial unique index where not null).

3. Rename `bingo_cells.target_template_id` to `target_definition_id`
- DB column is still `target_template_id`; Python API already moved to `target_definition_id`.
- Reason: this column points to `nfts.id` (definition id), not `nft_templates.id`.

## Strongly Recommended Schema Changes

4. Rename tables to match semantics
- `nfts` -> `nft_definitions`
- `user_nft_ownership` -> `nft_instances`

5. Align dependent FK column names
- In tables referencing `nfts.id`, decide whether column names should be `definition_id` (instead of `nft_id`) where semantics are definition-level.
- In tables referencing instance rows, use `ownership_id`/`instance_id` consistently.

6. Revisit `nft_templates` role
- If templates stay unused in production flows, either:
  - keep as optional authoring metadata with explicit lifecycle docs, or
  - deprecate/remove in a later migration.

## Migration Order (Safe Rollout)

1. Add new constraints/indexes first (non-breaking)
- Add unique index for `prize_draw_results(ownership_id, draw_type_id)` (nullable-safe strategy as needed).
- Add unique index for `user_nft_ownership(unique_nft_id)`.
- Add partial unique index for `user_nft_ownership(blockchain_nft_id)` where not null.

2. Backfill and validate data
- Ensure all `prize_draw_results` rows have correct `ownership_id` where resolvable.
- Detect duplicates before switching uniqueness.

3. Switch enforcement
- Drop old unique `uq_prize_draw_result_unique` on `(nft_id, draw_type_id)`.
- Drop `uq_user_nft_once` on `(user_id, nft_id)`.

4. Rename columns/tables (if approved)
- Apply table and column renames with matching ORM/alembic updates.
- Keep temporary compatibility views or aliases only if downstream systems need transition time.

5. Cleanup
- Remove temporary compatibility code paths and conflict guards in app logic after schema is live.

## Current Temporary App Guards (To Remove After Migration)

- Prize draw currently raises `ValueError` when multiple instances of one definition would collide on `(nft_id, draw_type_id)`.
- Batch draw pre-validates instance sets and rejects same-definition multi-instance batches under current schema.

These guards should be deleted once uniqueness is moved to `(ownership_id, draw_type_id)`.

## Verification Checklist After Schema Migration

1. Run local tests:
- `python -m pytest -q tests`

2. Run drift check against production-like DB:
- `python scripts/check_schema_drift.py`

3. Verify key workflows manually:
- issue multiple instances from same definition to same user and different users
- run single and batch prize draws on those instances
- confirm results persist independently per instance

4. Release process:
- bump `pyproject.toml` version
- tag release
- update transit API dependency pin
