# NICT Badge & Wallet System

This repository implements the **Badge & Wallet System** for the NICT project by Tohoku University. It manages NFT-based badges, bingo cards, and blockchain transactions.

## Project Structure

```
nict-badge-wallet-sys/
├─ nictbw/
│  ├─ db/               # DB engine, session, metadata, utilities
│  ├─ models/           # SQLAlchemy ORM 2.0 models
├─ scripts/
│  ├─ init_db.py        # create all tables in local SQLite
│  └─ seed_dev.py       # seed dev data
├─ README.md
└─ requirements.txt
```

---

## Quick Start

### 1. Install the library (in editable mode)

```bash
pip install -e .
```

### 2. Initialize the database

```bash
python scripts/init_db.py
python scripts/seed_dev.py
```

This creates `dev.db` (SQLite) with all schema objects.

### 3. Verify tables

The init script will print all created tables:

```
Created tables: admins, users, nft_conditions, nfts, user_nft_ownership, bingo_cards, bingo_cells, blockchain_transactions, audit_logs
```

---

## Switching Databases

Change the DB URL in `nictbw/db/engine.py`:

```python
DEFAULT_SQLITE_URL = "sqlite:///./dev.db"  # SQLite by default
```

---

## TODO List
* Add methods for querying and updating entities.
* Add bingo card generator that randomizes NFT assignments to cells.
* Update old files to adopt dotenv.
* Switch to @property instead of getter/setter methods for models.
* Update module imports to Python package style.
* Confirmation on format of unique_nft_id.
* Integrate with App API.
* Add Alembic.
---
