# NICT Badge & Wallet System

This repository implements the **Badge & Wallet System** for the NICT project by Tohoku University. It manages NFT-based badges, bingo cards, and blockchain transaction logs.

## Overview

### Key Features

* **Integrated Database** using SQLAlchemy ORM 2.0.
* **SQLite** for development (easy to switch to other databases).
* **Entities**:

  * Admins, Users
  * NFTs, NFT Conditions
  * NFT Ownership Tracking
  * Bingo Cards & Cells
  * Blockchain Transactions
  * Audit Logs

---

## Project Structure

```
nict-badge-wallet-sys/
├─ app/
│  ├─ db/               # DB engine, session, metadata
│  ├─ models/           # SQLAlchemy ORM 2.0 models
│  ├─ repositories/     # (planned) data access helpers
│  ├─ services/         # (planned) domain logic (bingo, NFT minting, etc.)
│  └─ utils/            # utility functions
├─ scripts/
│  ├─ init_db.py        # create all tables in local SQLite
│  └─ seed_dev.py       # seed dev data
├─ tests/               # (planned) unit tests
├─ README.md
└─ pyproject.toml / requirements.txt
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
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

Change the DB URL in `app/db/engine.py`:

```python
DEFAULT_SQLITE_URL = "sqlite:///./dev.db"  # default
```

---

## Next Steps

* Add methods for querying and updating entities.
* Add __repr__ for models.
* Integrate with API layer.
* Add Alembic migrations.

---
