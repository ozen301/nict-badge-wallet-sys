from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select
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
        return session.scalars(select(cls).where(cls.in_app_id == in_app_id)).first()

    def update_nickname(self, session: Session, new_nickname: str) -> None:
        self.nickname = new_nickname
        self.updated_at = datetime.now(timezone.utc)
        session.commit()

    def update_password_hash(self, session: Session, new_password_hash: str) -> None:
        self.password_hash = new_password_hash
        self.updated_at = datetime.now(timezone.utc)
        session.commit()
