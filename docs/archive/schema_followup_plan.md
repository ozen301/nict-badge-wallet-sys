## Plan: Full Schema Alignment Migration (v1.1.0)

> [!NOTE] Execution status (2026-03-03): 
> Phases 1 through 9 completed. Production schema updated successfully. Drift check now returns zero drift. Release tagging remains deferred to `main` after squash merge.

**TL;DR:** Two Alembic migrations bring the Postgres schema in line with the v1.0.0 ORM. Migration A (non-breaking) backfills `prize_draw_results.ownership_id` to NOT NULL and adds new unique indexes. Migration B (breaking) drops legacy constraints, renames 2 tables, renames 26 columns across 14 tables, and cascades FK/index name changes. ORM code then drops all `mapped_column("db_name", ...)` overrides, removes 3 temporary guards, and updates tests. Version bumps to 1.1.0.

**Steps**

### Phase 1 — Pre-migration data validation script

1. Create scripts/validate_pre_migration.py. This script connects to the production DB and checks:
   - `prize_draw_results` rows where `ownership_id IS NULL` — report count and IDs so we know what to backfill or decide on.
   - Duplicate `(ownership_id, draw_type_id)` pairs in `prize_draw_results` — would violate the new unique constraint.
   - Duplicate `unique_nft_id` values in `user_nft_ownership` — would violate the new unique index.
   - Duplicate non-null `blockchain_nft_id` values in `user_nft_ownership` — would violate the new partial unique index.
   - Any `prize_draw_results` rows where `ownership_id` cannot be resolved (orphaned references).
   - Output a pass/fail summary. This runs read-only against a production snapshot or staging.

### Phase 2 — Alembic Migration A: backfill + new constraints (non-breaking)

2. Create a new Alembic revision (down from `fb03c2018550`). This migration:
   - Backfills `prize_draw_results.ownership_id` for any NULL rows (strategy: resolve from `user_nft_ownership` via `nft_id + user_id`, or delete orphans — depends on validation results from step 1).
   - Alters `prize_draw_results.ownership_id` to `NOT NULL`.
   - Adds unique index `uq_prize_draw_result_instance` on `prize_draw_results(ownership_id, draw_type_id)`.
   - Adds unique index `uq_nft_instance_unique_id` on `user_nft_ownership(unique_nft_id)`.
   - Adds partial unique index `uq_nft_instance_blockchain_id` on `user_nft_ownership(blockchain_nft_id) WHERE blockchain_nft_id IS NOT NULL`.
   - **Does NOT drop** old constraints yet — both old and new coexist temporarily. This is safe to run with the current v1.0.0 code.

### Phase 3 — Alembic Migration B: drop old constraints + full rename

3. Create a second Alembic revision chained after Migration A. This is the breaking migration:

   **3a. Drop old unique constraints:**
   - Drop `uq_prize_draw_result_unique` on `prize_draw_results(nft_id, draw_type_id)`.
   - Drop `uq_user_nft_once` on `user_nft_ownership(user_id, nft_id)`.

   **3b. Rename tables:**
   - `nfts` → `nft_definitions`
   - `user_nft_ownership` → `nft_instances`

   **3c. Rename columns** (26 renames across 14 tables — Postgres `ALTER COLUMN ... RENAME` is metadata-only, no rewrite):

   | Table (post-rename) | Column old → new |
   |---|---|
   | `nft_instances` | `nft_id` → `definition_id`, `unique_nft_id` → `unique_instance_id` |
   | `bingo_cells` | `target_template_id` → `target_definition_id`, `nft_id` → `definition_id`, `matched_ownership_id` → `matched_nft_instance_id` |
   | `bingo_card_issue_tasks` | `center_nft_id` → `center_definition_id`, `ownership_id` → `nft_instance_id`, `unique_nft_ref` → `unique_instance_ref` |
   | `bingo_period_rewards` | `reward_nft_id` → `reward_definition_id` |
   | `pre_generated_bingo_cards` | `center_nft_id` → `center_definition_id`, `cell_nft_ids` → `cell_definition_ids` |
   | `coupon_templates` | `default_display_nft_id` → `default_display_definition_id` |
   | `nft_coupon_bindings` | `nft_id` → `definition_id` |
   | `coupon_instances` | `nft_id` → `definition_id`, `display_nft_id` → `display_definition_id`, `ownership_id` → `nft_instance_id` |
   | `coupon_stores` | `nft_id` → `definition_id` |
   | `nft_claim_requests` | `nft_id` → `definition_id`, `ownership_id` → `nft_instance_id` |
   | `prize_draw_results` | `nft_id` → `definition_id`, `ownership_id` → `nft_instance_id` |
   | `raffle_entries` | `ownership_id` → `nft_instance_id` |
   | `nft_conditions` | `required_nft_id` → `required_definition_id`, `prohibited_nft_id` → `prohibited_definition_id` |
   | `nft_templates` | `required_nft_id` → `required_definition_id`, `prohibited_nft_id` → `prohibited_definition_id` |

   **3d. Rename FK constraints** (drop + recreate with new names/references; ~25 FKs). Key examples:
   - `fk_user_nft_ownership_nft_id_nfts` → `fk_nft_instances_definition_id_nft_definitions`
   - `fk_prize_draw_results_nft_id_nfts` → `fk_prize_draw_results_definition_id_nft_definitions`
   - `fk_prize_draw_results_ownership_id_user_nft_ownership` → `fk_prize_draw_results_nft_instance_id_nft_instances`
   - All 13 FKs referencing `nfts.id` and 6 FKs referencing `user_nft_ownership.id` follow the same pattern.
   - The 4 FKs from the `nfts` table itself become `fk_nft_definitions_*`.

   **3e. Rename indexes** (~13 indexes):
   - `ix_nfts_id` → `ix_nft_definitions_id`
   - `ix_user_nft_ownership_id` → `ix_nft_instances_id`
   - `ix_bingo_cells_target_template_id` → `ix_bingo_cells_target_definition_id`
   - etc. — follow pattern `ix_{table}_{new_column}`.

   **3f. Rename remaining unique constraint:**
   - `bingo_card_issue_tasks_ownership_id_key` → `bingo_card_issue_tasks_nft_instance_id_key`
   - Update names of the two new indexes from Migration A if they referenced old columnnames (they should already use new semantic names).

### Phase 4 — ORM code changes

4. Update `__tablename__` in:
   - nft.py — `NFTDefinition.__tablename__ = "nft_definitions"`
   - ownership.py — `NFTInstance.__tablename__ = "nft_instances"`

5. Remove all `mapped_column("db_name", ...)` name overrides across model files, since DB column names now match ORM property names. Affected files:
   - nft.py — `NFTCondition` (2 columns), `NFTTemplate` (2 columns)
   - ownership.py — `NFTInstance` (2 columns)
   - prize_draw.py — `PrizeDrawResult` (2 columns), `RaffleEntry` (1 column)
   - bingo.py — `BingoCell` (3 columns), `BingoCardIssueTask` (3 columns), `BingoPeriodReward` (1 column), `PreGeneratedBingoCard` (2 columns)
   - coupon.py — `CouponTemplate` (1), `NFTCouponBinding` (1), `CouponInstance` (3), `CouponStore` (1)
   - misc.py — `NFTClaimRequest` (2 columns)

6. Update `__table_args__` unique constraint definitions:
   - prize_draw.py — Replace `UniqueConstraint("nft_id", "draw_type_id", name="uq_prize_draw_result_unique")` with `UniqueConstraint("nft_instance_id", "draw_type_id", name="uq_prize_draw_result_instance")`.
   - ownership.py — Remove `UniqueConstraint("user_id", "nft_id", name="uq_user_nft_once")`. Add `UniqueConstraint("unique_instance_id", name="uq_nft_instance_unique_id")` and the partial index for `blockchain_nft_id`.

### Phase 5 — Remove temporary guards

7. In engine.py — Simplify `_upsert_result()` (~lines 291–305): remove the fallback-to-definition lookup branch and the `ValueError` raise. Lookup should be solely by `(nft_instance_id, draw_type_id)`.

8. In workflows.py — Delete `_validate_instances_compatible_with_result_uniqueness()` entirely (~lines 271–293) and remove its call from `run_prize_draw_batch()` (~line 434).

9. In nft.py — Remove the duplicate-check guard in `NFTDefinition.issue_dbwise_to_user()` (~lines 216–218) that raises `ValueError("User already owns this NFT definition")`.

10. In ownership.py — Review `NFTInstance.get_by_user_and_definition()` which uses `.one_or_none()`. Post-migration, multiple instances per (user, definition) are allowed. Change to `.first()` or rename to indicate it returns an arbitrary match, and audit its 3 callers:
    - `issue_dbwise_to_user` — guard removed in step 9, so this call goes away.
    - `User.sync_nft_instances_from_chain` in user.py (~line 452) — needs logic review to handle multiple instances.
    - `User.unlock_cells_for_definition` in user.py (~line 262) — needs logic review.

### Phase 6 — Update tests

11. In test_prize_draw_workflow.py:
    - Remove or rewrite `test_run_prize_draw_batch_raises_on_same_definition_instances` — instead test that batch draws on multiple instances of the same definition **succeed**.
    - Remove or rewrite `test_run_prize_draw_raises_on_conflicting_existing_definition_result` — instead test that two instances of the same definition can each store independent results.

12. In test_models.py:
    - Update `test_user_issue_nft_creates_ownership_and_increments` to verify that issuing a second instance of the same definition to the same user now **succeeds** instead of raising.

13. Run full test suite: `conda activate nict && python -m pytest -q tests`

### Phase 7 — Update API adapter

14. In models.py — The 24 SQLAlchemy synonyms mapping legacy ORM attribute names to new ones can be **simplified or removed** since DB column names now match ORM names. The synonym registrations still work but are unnecessary overhead. Update the `NFT`/`UserNFTOwnership` backward-compatibility aliases if needed.

### Phase 8 — Drift check + version bump

15. Run `conda activate nict && python scripts/check_schema_drift.py` against a local DB with both migrations applied — confirm zero drift.

16. Bump version in pyproject.toml to `1.1.0`.

17. Update schema_followup_memo.md — mark all items as completed, note migration revision IDs.

18. Tag release `v1.1.0`.

### Phase 9 — Production rollout

19. **Pre-flight:**
    - Take a full `pg_dump` backup of production.
    - Run the validation script (step 1) against production to confirm data is clean.
    - Deploy Migration A to a staging environment first and verify with drift check.

20. **Deploy Migration A** (non-breaking):
    - `alembic upgrade +1` — adds new indexes/constraints, backfills ownership_id.
    - Current v1.0.0 API code continues to work normally (old + new constraints coexist).
    - Verify application health.

21. **Deploy Migration B + code** (breaking, requires maintenance window):
    - Stop API service.
    - `alembic upgrade head` — renames tables, columns, drops old constraints.
    - Deploy updated `nict-bw` v1.1.0 package (with ORM changes from phases 4–6).
    - Deploy updated API code (with adapter changes from phase 7).
    - Start API service.
    - Run smoke tests (issue instance, run draw, check bingo).

22. **Rollback plan:**
    - Migration A: `alembic downgrade -1` (drops new indexes, restores nullable ownership_id).
    - Migration B: `alembic downgrade -1` (reverses all renames, restores old constraints). Requires rolling back to v1.0.0 code simultaneously.

**Verification**
- `python scripts/validate_pre_migration.py` — pre-migration data check
- `python -m pytest -q tests` — full test suite after ORM changes
- `python scripts/check_schema_drift.py` — zero drift post-migration
- Manual: issue multiple instances of same definition to same user; run batch prize draw on them; confirm independent results

**Decisions**
- **Full rename scope**: tables + columns in one release, not incremental — avoids prolonged mismatch period
- **NOT NULL** for `prize_draw_results.nft_instance_id` (was `ownership_id`): cleaner constraint, requires backfill
- **Two Alembic migrations**: A is non-breaking (can deploy independently), B is breaking (requires coordinated code deploy)
- **FK/index renames**: done for consistency, not strictly required (Postgres tracks by OID), but prevents confusion in future schema inspection