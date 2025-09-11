from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT, NFTTemplate
    from .ownership import UserNFTOwnership


class BingoCard(Base):
    """Bingo card assigned to a user.

    Represents a 3x3 grid of :class:`BingoCell` objects that can be unlocked by
    collecting NFTs matching predefined templates.
    """

    def __init__(
        self,
        user_id: int,
        issued_at: datetime,
        completed_at: Optional[datetime] = None,
        state: str = "active",
    ):
        self.user_id = user_id
        self.issued_at = issued_at
        self.completed_at = completed_at
        self.state = state

    __tablename__ = "bingo_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    user: Mapped["User"] = relationship(back_populates="bingo_cards")
    cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("state IN ('active','completed','expired')", name="state_enum"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCard(id={self.id}, user_id={self.user_id}, "
            f"issued_at={self.issued_at}, state='{self.state}')>"
        )

    # Convenience helpers
    @property
    def winning_lines(self) -> list[tuple[int, int, int]]:
        """Get all possible winning line combinations for a 3x3 bingo card."""
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

    @property
    def completed_lines(self) -> list[tuple[int, int, int]]:
        """All completed lines in the bingo card.

        The result is a list of tuples containing the indices of cells that form
        completed lines. Each tuple represents the positions of cells in a winning
        line that are all in ``"unlocked"`` state.
        """
        result: list[tuple[int, int, int]] = []
        for a, b, c in self.winning_lines:
            if all(
                cell.state == "unlocked"
                for cell in (self.cells[a], self.cells[b], self.cells[c])
            ):
                result.append((a, b, c))
        return result


class BingoCell(Base):
    """Single cell within a :class:`BingoCard` grid."""

    def __init__(
        self,
        bingo_card_id: int,
        idx: int,
        target_template_id: int,
        nft_id: Optional[int] = None,
        matched_ownership_id: Optional[int] = None,
        state: str = "locked",
        unlocked_at: Optional[datetime] = None,
    ):
        self.bingo_card_id = bingo_card_id
        self.idx = idx
        self.target_template_id = target_template_id
        self.nft_id = nft_id
        self.matched_ownership_id = matched_ownership_id
        self.state = state
        self.unlocked_at = unlocked_at

    __tablename__ = "bingo_cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bingo_card_id: Mapped[int] = mapped_column(
        ForeignKey("bingo_cards.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    target_template_id: Mapped[int] = mapped_column(
        ForeignKey("nft_templates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_ownership_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    card: Mapped["BingoCard"] = relationship(back_populates="cells")
    target_template: Mapped["NFTTemplate"] = relationship(back_populates="target_cells")
    nft: Mapped[Optional["NFT"]] = relationship(back_populates="target_cell")
    matched_ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        back_populates="matched_cells"
    )

    __table_args__ = (
        UniqueConstraint("bingo_card_id", "idx", name="uq_card_idx"),
        CheckConstraint("state IN ('locked','unlocked')", name="state_enum"),
        CheckConstraint(
            "(state = 'locked' AND nft_id IS NULL AND matched_ownership_id IS NULL) OR "
            "(state = 'unlocked' AND nft_id IS NOT NULL AND matched_ownership_id IS NOT NULL)",
            name="locked_unlocked_consistency",
        ),
        CheckConstraint("idx >= 0 AND idx <= 8", name="idx_range"),
        Index("ix_bingo_cells_card", "bingo_card_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCell(id={self.id}, idx={self.idx}, target_template_id={self.target_template_id}, "
            f"nft_id={self.nft_id}, state='{self.state}')>"
        )
