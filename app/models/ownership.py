from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from . import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT
    from .bingo import BingoCell


class UserNFTOwnership(Base):
    __tablename__ = "user_nft_ownership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nft_id: Mapped[int] = mapped_column(
        ForeignKey("nfts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_nft_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    other_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ownerships")
    nft: Mapped["NFT"] = relationship(back_populates="ownerships")
    matched_cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="matched_ownership"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "nft_id", name="uq_user_nft"),
        UniqueConstraint(
            "nft_id", "serial_number", name="uq_nft_serial"
        ),  # recommended
        Index("ix_unique_nft_id", "unique_nft_id"),
    )
