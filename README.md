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
pip install -e . --config-settings editable_mode=strict
```

### 2. Configure .env file
Copy `.env.example` to `.env` and modify as needed.

### 3. Initialize the database
```bash
python scripts/init_db.py
python scripts/seed_dev.py  # optional, seed dev data
```

This creates all schema objects in the database configured by `DB_URL`. The `init_db.py` script will print all tables present after migration:

```
Current tables: admins, app_banners, bingo_card_issue_tasks, bingo_cards, bingo_cells, bingo_periods, coupon_instances, coupon_player_store_inventories, coupon_players, coupon_stores, coupon_templates, external_accounts, nft_claim_requests, nft_conditions, nft_coupon_bindings, nft_templates, nfts, pre_generated_bingo_cards, pre_minted_users, prize_draw_results, prize_draw_types, prize_draw_winning_numbers, raffle_entries, raffle_events, system_configurations, user_nft_ownership, users
```

---

## Switch Databases
Simply change the `DB_URL` variable in `.env`:

```python
DB_URL="postgresql://user:password@localhost:5432/nictdevdb"  # PostgreSQL recommended

# Optional local SQLite:
# DB_URL="sqlite:///./dev.db"
```

Any URL supported by SQLAlchemy is valid here.

## Database migrations (Alembic)
We use [Alembic](https://alembic.sqlalchemy.org/) to keep the SQL schema in sync with the ORM models. Older revisions were archived in `alembic/versions_legacy` when the API-aligned baseline was created.

Common commands (run from the repo root):

```bash
# Create a new migration after editing the SQLAlchemy models
alembic revision --autogenerate -m "describe change"

# Apply all migrations to the target DB (uses DB_URL from .env by default)
alembic upgrade head

# Step backwards if needed
alembic downgrade -1
```

### Production baseline (one-time)
Production previously did not track Alembic revisions. To start tracking without changing schema, stamp the baseline once:

```bash
alembic stamp 9624f3823ec4
```

After stamping, future migrations can be applied with `alembic upgrade head`.

You can override the database URL for one-off commands without editing `.env` by prefixing the command with the desired `DB_URL`. For example, to run migrations on a temporary SQLite DB:

```bash
DB_URL=sqlite:///./temp.db alembic upgrade head
```

That shell prefix temporarily sets `DB_URL` only for the single command, so your `.env` and running services stay untouched.

The generated migration scripts live in `alembic/versions/`.

### Schema drift guard
To detect drift between the ORM metadata and the live database schema, run:

```bash
python scripts/check_schema_drift.py
```

The script exits non-zero when differences are detected and prints the operations Alembic would generate.

---

## Documentation and Examples
See [docs/workflows.md](./docs/workflows.md) for common workflows. The workflows encapsulate typical sequences of operations using the models defined in this project.

Check the Jupyter notebook [docs/code_examples.ipynb](./docs/code_examples.ipynb) for practical usage of these workflows. The notebook provides runnable examples including:
- Setting up the database engine and models
- Basic CRUD with SQLAlchemy 2.0
- Using the models defined in this project to create users, NFTs, etc.
- Common workflows such as user registration, NFT issuance, prize draw operations, etc.

---
