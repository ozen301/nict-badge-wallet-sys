# NICT Badge & Wallet System

This repository implements the **Badge & Wallet System** for the NICT project carried out by Tohoku University. It manages NFT-based badges, bingo cards, and blockchain transactions.

## Project Structure

```
nict-badge-wallet-sys/
├─ nictbw/
│  ├─ blockchain/       # Blockchain API interaction
│  ├─ db/               # DB engine, session, metadata, utilities
│  ├─ models/           # SQLAlchemy ORM 2.0 models
├─ scripts/
│  ├─ init_db.py        # create all tables in local SQLite
│  └─ seed_dev.py       # seed dev data
├─ .env.example         # environment variables
├─ README.md
└─ pyproject.toml
```

---

## Quick Start

### 1. Install the library (in editable mode)

```bash
pip install -e .
```

### 2. Configure .env file
Copy `.env.example` to `.env` and modify as needed.

### 3. Initialize the database

```bash
python scripts/init_db.py
python scripts/seed_dev.py  # optional, seed dev data
```

This creates `dev.db` (SQLite) with all schema objects.

### 4. Verify tables

The init script will print all created tables:

```
Created tables: admins, users, nft_conditions, nfts, user_nft_ownership, bingo_cards, bingo_cells, blockchain_transactions, audit_logs
```

---

## Switching Databases

Change the DB URL in `.env`:

```python
DB_URL="sqlite:///./dev.db"  # SQLite by default
```

Any URL supported by SQLAlchemy is valid here.

---

## TODO
* Add methods for querying and updating entities.
* Add bingo card generator that randomizes NFT assignments to cells.
* Include NFT metadata in blockchain related operations.
* Update old files to adopt dotenv.
* Switch to @property instead of getter/setter methods for models.
* Update module imports to Python package style.
* Confirmation on format of unique_nft_id.
* Integrate with App API.
* Add Alembic.
---
