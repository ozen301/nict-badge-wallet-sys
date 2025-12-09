# NICT Badge & Wallet System

This repository implements the **Badge & Wallet System** for the NICT project carried out by Tohoku University, including the database layer that stores all badge, wallet, bingo, prize-draw, and blockchain records.

## Project Structure

```
nict-badge-wallet-sys/
├─ alembic/             # Alembic env + migration scripts
├─ docs/
│  ├─ code_examples.ipynb  # Jupyter notebook with code examples
│  ├─ workflows.md         # Common workflows documentation
├─ nictbw/
│  ├─ blockchain/       # Blockchain API interaction
│  ├─ db/               # DB engine, session, metadata, utilities
│  ├─ models/           # SQLAlchemy ORM 2.0 models
│  ├─ prize_draw/       # Prize draw logic
│  ├─ workflows.py      # Common workflows encapsulation
├─ scripts/             # utility scripts
├─ tests/               # unit tests
├─ alembic.ini          # Alembic CLI configuration
├─ .env.example         # environment variables example
├─ README.md
└─ pyproject.toml
```

---

## Quick Start

### Prerequisites
- Python >= 3.11

### 1. Install the library (in editable mode)
```bash
git clone https://github.com/ozen301/nict-badge-wallet-sys.git
cd nict-badge-wallet-sys
pip install -e .
```

### 2. Configure .env file
Copy `.env.example` to `.env` and modify as needed.

### 3. Initialize the database
```bash
python scripts/init_db.py
python scripts/seed_dev.py  # optional, seed dev data
```

This by default creates `dev.db` (SQLite) with all schema objects. The `init_db.py` script will print all tables present after migration:

```
Current tables: admins, audit_logs, bingo_cards, bingo_cells, blockchain_transactions, coupon_instances, coupon_templates, nft_conditions, nft_coupon_bindings, nft_templates, nfts, prize_draw_results, prize_draw_types, prize_draw_winning_numbers, user_nft_ownership, users
```

> `scripts/init_db.py` now wraps `alembic upgrade head`, so running it or executing Alembic directly yields the same schema state.
---

## Switch Databases
Simply change the `DB_URL` variable in `.env`:

```python
DB_URL="sqlite:///./dev.db"  # SQLite by default

# Example PostgreSQL URL:
# DB_URL="postgresql://user:password@localhost:5432/nictdevdb"
```

Any URL supported by SQLAlchemy is valid here.

## Database migrations (Alembic)
We use [Alembic](https://alembic.sqlalchemy.org/) to keep the SQL schema in sync with the ORM models.

Common commands (run from the repo root):

```bash
# Create a new migration after editing the SQLAlchemy models
alembic revision --autogenerate -m "describe change"

# Apply all migrations to the target DB (uses DB_URL from .env by default)
alembic upgrade head

# Step backwards if needed
alembic downgrade -1
```

You can override the database URL for one-off commands without editing `.env` by prefixing the command with the desired `DB_URL`. For example, to run migrations on a temporary SQLite DB:

```bash
DB_URL=sqlite:///./temp.db alembic upgrade head
```

That shell prefix temporarily sets `DB_URL` only for the single command, so your `.env` and running services stay untouched.

The generated migration scripts live in `alembic/versions/`.

---

## Documentation and Examples
See [docs/workflows.md](./docs/workflows.md) for common workflows. The workflows encapsulate typical sequences of operations using the models defined in this project.

Check the Jupyter notebook [docs/code_examples.ipynb](./docs/code_examples.ipynb) for practical usage of these workflows. The notebook provides runnable examples including:
- Setting up the database engine and models
- Basic CRUD with SQLAlchemy 2.0
- Using the models defined in this project to create users, NFTs, etc.
- Common workflows such as user registration, NFT issuance, prize draw operations, etc.

---