# Schema Follow-Up Memo (Completed in Code / Pending Production Rollout)

Date: 2026-03-02

## Summary
The schema/code alignment work planned after the v1.0.0 semantic refactor has been completed in this repository through Phase 8 preparation.

Completed in this branch:
- Alembic Migration A (non-breaking): `a1b2c3d4e5f6`
- Alembic Migration B (breaking rename migration): `b6f3e4c9d8a1`
- ORM model/table/column alignment for definition-first and instance-first naming.
- Removal of temporary app guards that blocked same-definition multi-instance draw persistence.
- Test updates for new instance-based behavior.
- API adapter simplification (legacy synonym registration removed; compatibility aliases remain).
- Package version bump to `1.1.0`.

## Migration Revisions
- `a1b2c3d4e5f6` (Revises `fb03c2018550`)
  - backfills `prize_draw_results.ownership_id`
  - enforces NOT NULL on ownership reference
  - adds:
    - `uq_prize_draw_result_instance`
    - `uq_nft_instance_unique_id`
    - `uq_nft_instance_blockchain_id` (partial unique)
- `b6f3e4c9d8a1` (Revises `a1b2c3d4e5f6`)
  - drops legacy unique constraints
  - renames tables:
    - `nfts` -> `nft_definitions`
    - `user_nft_ownership` -> `nft_instances`
  - renames dependent columns, FK names, index names, and remaining unique names

## Current Verification Status
- Unit/integration tests (repo):
  - `python -m pytest -q tests` -> passed
- Drift check against the currently configured DB:
  - currently shows drift until Migration B is applied in that environment.
  - this is expected while DB schema is still pre-rename.

## Production Rollout Status
- Rollout is prepared but not executed in this branch.
- Release tag is intentionally deferred per workflow: tag on `main` after squash merge.

## Post-Merge Actions
1. Execute production/staging runbook for Migration B + code deploy during maintenance window.
2. Re-run `python scripts/check_schema_drift.py` against the upgraded DB and confirm zero drift.
3. Tag `v1.1.0` on `main` after squash merge.
4. Update dependent API/service package pins to `v1.1.0`.
