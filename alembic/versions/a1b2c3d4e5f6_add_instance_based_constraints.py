"""add instance-based constraints

Add new unique constraints needed for instance-first semantics:

- prize_draw_results.ownership_id becomes NOT NULL
- New unique on prize_draw_results(ownership_id, draw_type_id)
- New unique on user_nft_ownership(unique_nft_id)
- New partial unique on user_nft_ownership(blockchain_nft_id) WHERE NOT NULL

Old constraints are intentionally left in place so that v1.0.0 code remains
compatible.  They will be dropped in the next migration.

Revision ID: a1b2c3d4e5f6
Revises: fb03c2018550
Create Date: 2026-03-02 17:02:00.000000

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'fb03c2018550'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # -- prize_draw_results: backfill ownership_id from (nft_id, user_id) ------
    # Deterministic strategy: map each NULL row to the latest ownership record
    # for the same (nft_id, user_id). If any rows remain NULL after this update,
    # abort migration so data can be remediated explicitly.
    op.execute(
        sa.text(
            """
            WITH ownership_candidates AS (
                SELECT
                    pdr.id AS result_id,
                    uno.id AS ownership_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY pdr.id
                        ORDER BY uno.id DESC
                    ) AS rn
                FROM prize_draw_results pdr
                JOIN user_nft_ownership uno
                  ON uno.nft_id = pdr.nft_id
                 AND uno.user_id = pdr.user_id
                WHERE pdr.ownership_id IS NULL
            )
            UPDATE prize_draw_results pdr
               SET ownership_id = oc.ownership_id
              FROM ownership_candidates oc
             WHERE pdr.id = oc.result_id
               AND oc.rn = 1
               AND pdr.ownership_id IS NULL
            """
        )
    )

    unresolved_count = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM prize_draw_results WHERE ownership_id IS NULL"
        )
    ).scalar_one()
    if unresolved_count > 0:
        raise RuntimeError(
            "Cannot set prize_draw_results.ownership_id to NOT NULL: "
            f"{unresolved_count} rows remain unresolved after backfill."
        )

    # -- prize_draw_results: make ownership_id NOT NULL -------------------------
    with op.batch_alter_table('prize_draw_results', schema=None) as batch_op:
        batch_op.alter_column(
            'ownership_id',
            existing_type=sa.BigInteger(),
            nullable=False,
        )

    # -- prize_draw_results: new instance-based unique constraint ---------------
    op.create_unique_constraint(
        'uq_prize_draw_result_instance',
        'prize_draw_results',
        ['ownership_id', 'draw_type_id'],
    )

    # -- user_nft_ownership: unique on unique_nft_id ----------------------------
    op.create_unique_constraint(
        'uq_nft_instance_unique_id',
        'user_nft_ownership',
        ['unique_nft_id'],
    )

    # -- user_nft_ownership: partial unique on blockchain_nft_id ----------------
    # Partial unique index — only enforced when blockchain_nft_id is not null.
    # Using create_index with unique=True and a postgresql_where clause.
    op.create_index(
        'uq_nft_instance_blockchain_id',
        'user_nft_ownership',
        ['blockchain_nft_id'],
        unique=True,
        postgresql_where=sa.text('blockchain_nft_id IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop new constraints/indexes in reverse order
    op.drop_index(
        'uq_nft_instance_blockchain_id',
        table_name='user_nft_ownership',
    )

    op.drop_constraint(
        'uq_nft_instance_unique_id',
        'user_nft_ownership',
        type_='unique',
    )

    op.drop_constraint(
        'uq_prize_draw_result_instance',
        'prize_draw_results',
        type_='unique',
    )

    # Restore ownership_id to nullable
    with op.batch_alter_table('prize_draw_results', schema=None) as batch_op:
        batch_op.alter_column(
            'ownership_id',
            existing_type=sa.BigInteger(),
            nullable=True,
        )
