"""add raw tx data to nft instances

Revision ID: c9e12a7d4b20
Revises: b6f3e4c9d8a1
Create Date: 2026-03-03 10:59:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9e12a7d4b20"
down_revision: Union[str, Sequence[str], None] = "b6f3e4c9d8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("nft_instances", schema=None) as batch_op:
        batch_op.add_column(sa.Column("raw_tx_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("nft_instances", schema=None) as batch_op:
        batch_op.drop_column("raw_tx_data")
