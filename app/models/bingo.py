from __future__ import annotations
from datetime import datetime
from typing import Iterable, TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    select,
)
from . import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT
    from .ownership import UserNFTOwnership


class BingoCard(Base):
    __tablename__ = "bingo_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grid_size: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    user: Mapped["User"] = relationship(back_populates="bingo_cards")
    cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("state IN ('active','completed','expired')", name="state_enum"),
    )

    # Convenience helpers (sync ORM)
    def winning_lines(self) -> list[tuple[int, int, int]]:
        if self.grid_size != 3:
            return []
        return [
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        ]

    def is_line_complete(self) -> bool:
        cell_by_idx = {c.idx: c for c in self.cells}
        for a, b, c in self.winning_lines():
            if all(
                cell_by_idx.get(i) and cell_by_idx[i].state == "unlocked"
                for i in (a, b, c)
            ):
                return True
        return False


class BingoCell(Base):
    __tablename__ = "bingo_cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bingo_card_id: Mapped[int] = mapped_column(
        ForeignKey("bingo_cards.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    target_nft_id: Mapped[int] = mapped_column(
        ForeignKey("nfts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    matched_ownership_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    card: Mapped["BingoCard"] = relationship(back_populates="cells")
    target_nft: Mapped["NFT"] = relationship(back_populates="target_cells")
    matched_ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        back_populates="matched_cells"
    )

    __table_args__ = (
        UniqueConstraint("bingo_card_id", "idx", name="uq_card_idx"),
        CheckConstraint("state IN ('locked','unlocked')", name="state_enum"),
        CheckConstraint("idx >= 0 AND idx <= 8", name="idx_range_3x3"),
        CheckConstraint(
            "(state = 'locked' AND matched_ownership_id IS NULL) OR (state = 'unlocked' AND matched_ownership_id IS NOT NULL)",
            name="locked_unlocked_consistency",
        ),
        Index("ix_bingo_cells_card", "bingo_card_id"),
    )
