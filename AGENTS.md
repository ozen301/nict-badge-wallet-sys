# AGENTS.md

## Overview
The **NICT Project** (Tohoku University, Japan) pilots a blockchain-based reward system to stimulate local economies.  
During the November 2025 basketball series, users earn NFT badges for attending games and visiting partner restaurants.  
Badges enable **bingo gameplay** and a **prize draw** mechanism.

---

## System Architecture
| Component                                   | Function                                                             |
| ------------------------------------------- | -------------------------------------------------------------------- |
| **API Gateway**                             | Handles routing, authentication, and rate limiting.                  |
| **Badge & Wallet System (This Repository)** | SQLAlchemy backend managing users, wallets, bingo state, and prize-draw selection/winner computation. Coupons are handled by the API. |
| **Badge App**                               | Mobile/web interface for displaying badges and rewards.              |
| **Blockchain (YenPoint)**                   | External service minting NFTs on Bitcoin SV.                         |

**Flow:**  
User → App → API → Badge & Wallet → Blockchain  

---

## NFT & Gameplay Flow
1. Users receive NFT badges via the app.  
2. Badges of specific types initiate a **3×3 bingo** (1 game badge + 8 restaurant/event goals).  
3. Completing a line grants rewards.

---

## Prize-Draw System

### Purpose
Each NFT deterministically produces a **draw number** from its `origin`.  
This value is compared with a **winning number** to determine outcomes — instant or event-based.

### Data Model
- **PrizeDrawType** – defines algorithm and thresholds.  
- **PrizeDrawWinningNumber** – stores winning numbers.  
- **PrizeDrawResult** – stores outcomes for specific NFT instances (with associated definition and user context).
- Coupons are now API-managed; this repository returns winning NFT-instance/user pairs only.

### Draw Execution (current)
- Bingo draws: entries are NFT instances that sit on any completed bingo line; each instance is one entry.
- Final-day draw: entries are only the final-day attendance-stamp NFT instances (independent of bingo lines).
- Ranking uses the existing per-instance draw-number algorithm; ties at the cutoff all win.
- The API orchestrates draw scheduling/events and handles coupon issuance/carry-over. This repo exposes workflows to select entries and compute winners.

---

## Schema Sync Notes
- Production Postgres is the source of truth for schema shape.
- Alembic baseline revision: `9624f3823ec4` (older revisions archived in `alembic/versions_legacy`).
- Use `python scripts/check_schema_drift.py` to detect ORM vs live DB drift.
- When schema changes, bump `pyproject.toml` version, tag a release, and update API dependency.

## Recent Integration Notes
- Released `v1.0.0` from this repo (pyproject version updated to 1.0.0).
- `v1.0.0` is a hard-break semantic refactor:
  - `NFTDefinition` is definition metadata (`nfts` table).
  - `NFTInstance` is issued/owned instances (`user_nft_ownership` table).
  - Prize draws evaluate NFT instances.
- DB schema is intentionally unchanged in `v1.0.0`; follow-up schema tasks are tracked in `docs/schema_followup_memo.md`.
- Added API adapter: `_api_ref/nft_transit_api/app/models.py` statically re-exports `nictbw.models` (Pylance-friendly).
- API `app/db.py` uses `nictbw.models.Base`; API dependency should be pinned to the released `v1.0.0` tag.
- Compatibility tweaks in `nictbw`: `BingoCard.is_expired` added; broken `RaffleEntry.__init__` removed.
- API main has newer period-based bingo changes (BingoPeriodReward, user_id+period_id uniqueness) not in prod; avoid merging until prod schema is updated.
- API docs updated: `_api_ref/nft_transit_api/docs/ja/DEVELOPMENT.md` includes schema update procedure.
- `_api_ref/` is a local reference clone and is not part of the `nict-bw` repo; it may not be present in future sessions.
