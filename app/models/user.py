from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select

from .nft import NFT
from .ownership import UserNFTOwnership
from . import Base

if TYPE_CHECKING:
    from .ownership import UserNFTOwnership
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    in_app_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    wallet: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

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

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, in_app_id='{self.in_app_id}', "
            f"nickname='{self.nickname}', updated_at='{self.updated_at}')>"
        )

    @classmethod
    def get_by_in_app_id(cls, session: Session, in_app_id: str) -> User | None:
        return session.scalar(select(cls).where(cls.in_app_id == in_app_id))

    @classmethod
    def get_by_wallet(cls, session: Session, wallet: str) -> User | None:
        return session.scalar(select(cls).where(cls.wallet == wallet))

    def set_nickname(self, new_nickname: str) -> None:
        self.nickname = new_nickname
        self.updated_at = datetime.now(timezone.utc)

    def set_password_hash(self, new_password_hash: str | None) -> None:
        if new_password_hash is None:
            self.password_hash = None
        else:
            self.password_hash = new_password_hash
        self.updated_at = datetime.now(timezone.utc)

    def verify_password_hash(self, password_hash: str) -> bool:
        return self.password_hash is not None and self.password_hash == password_hash

    def issue_nft(self, session: Session, nft: NFT) -> None:
        # minted_count = nft.minted_count if nft.minted_count is not None else 0
        new_ownership = UserNFTOwnership(
            user=self,
            nft=nft,
            serial_number=nft.minted_count,
            unique_nft_id=nft.prefix
            + "-"
            + str(nft.minted_count),  # Need confirmation on format of unique_nft_id
            acquired_at=nft.created_at,
        )
        self.ownerships.append(new_ownership)

        nft.minted_count += 1  # Increment the minted count
