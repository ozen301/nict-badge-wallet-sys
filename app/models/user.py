from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, DateTime
from . import Base

if TYPE_CHECKING:
    from .ownership import UserNFTOwnership
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # relationships
    ownerships: Mapped[list["UserNFTOwnership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bingo_cards: Mapped[list["BingoCard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chain_txs: Mapped[list["BlockchainTransaction"]] = relationship(
        back_populates="user"
    )
