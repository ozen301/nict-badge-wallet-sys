# v1.1.0 Rollout Runbook (No Tag in Feature Branch)

Date: 2026-03-02

This runbook covers Phase 9 operations for deploying schema/code alignment to production.
Per branch policy, **do not tag in this branch**. Tag only on `main` after squash merge.

> [!NOTE] Execution Record
> - Production rollout completed.
> - Post-deploy drift check completed successfully:
>  - `conda activate nict && python scripts/check_schema_drift.py` -> exit code `0`.
> - Tagging still deferred to `main`.

## Scope
- Applies Migration A + Migration B schema plan with coordinated code deployment.
- Assumes `nict-bw` code changes through Phase 8 are already merged.

## Preconditions
- Confirm working branch has:
  - Migration A: `a1b2c3d4e5f6`
  - Migration B: `b6f3e4c9d8a1`
  - `pyproject.toml` version `1.1.0`
- Confirm tests are green:
  - `conda activate nict && python -m pytest -q tests`

## Pre-Flight (Required)
1. Take full backup:
   - `pg_dump` of production DB before migration window.
2. Run pre-migration validator against production snapshot/DB:
   - `conda activate nict && python scripts/validate_pre_migration.py`
3. Staging rehearsal:
   - Apply Migration A then Migration B with matching code.
   - Run smoke tests and `python scripts/check_schema_drift.py`.

## Deployment Sequence

### Step 1: Non-breaking migration (if not already applied)
- `alembic upgrade a1b2c3d4e5f6`
- Verify application health with current v1.0.0-compatible runtime.

### Step 2: Breaking migration + code deploy (maintenance window)
1. Stop API/workers.
2. Apply schema head:
   - `alembic upgrade head`
3. Deploy updated packages/code:
   - `nict-bw` `1.1.0`
   - transit/API code aligned to renamed schema
4. Start API/workers.

## Post-Deploy Validation
1. Drift check:
   - `conda activate nict && python scripts/check_schema_drift.py`
   - Expected: zero drift.
2. Smoke tests:
   - issue multiple instances for same definition/user
   - run batch prize draw over those instances
   - confirm independent per-instance result persistence
3. Operational checks:
   - API error rates, background jobs, DB constraints/index usage

## Rollback
- If only Migration B/code causes issues:
  - stop services
  - `alembic downgrade -1`
  - redeploy v1.0.0-compatible code
  - start services
- If Migration A also needs rollback:
  - `alembic downgrade -1` again (from `a1b2c3d4e5f6` to `fb03c2018550`)
  - verify nullable ownership compatibility and old constraints

## Release Management (Deferred Tagging)
- After squash merge to `main`:
  1. verify `main` contains revisions `a1b2c3d4e5f6`, `b6f3e4c9d8a1`
  2. verify `pyproject.toml` is `1.1.0`
  3. create tag on `main`:
     - `git tag v1.1.0`
     - `git push origin v1.1.0`
