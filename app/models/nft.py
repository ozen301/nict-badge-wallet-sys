from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
    select,
    func,
)
from . import Base

if TYPE_CHECKING:
    from .ownership import UserNFTOwnership
    from .bingo import BingoCell
    from .chain import BlockchainTransaction


class NFTCondition(Base):
    __tablename__ = "nft_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    location_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    prohibited_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    other_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # backrefs set on NFT via foreign keys

    def __repr__(self) -> str:
        return (
            f"<NFTCondition(id={self.id}, start_time={self.start_time}, "
            f"end_time={self.end_time}, location_range='{self.location_range}', "
            f"updated_at={self.updated_at})>"
        )


class NFT(Base):
    __tablename__ = "nfts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    nft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nft_conditions.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # relationships
    condition: Mapped[Optional[NFTCondition]] = relationship(foreign_keys=[condition_id])
    ownerships: Mapped[list["UserNFTOwnership"]] = relationship(back_populates="nft")
    target_cells: Mapped[list["BingoCell"]] = relationship(back_populates="target_nft")
    chain_txs: Mapped[list["BlockchainTransaction"]] = relationship(
        back_populates="nft"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive','archived')", name="status_enum"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NFT(id={self.id}, prefix='{self.prefix}', shared_key='{self.shared_key}', "
            f"name='{self.name}', condition_id={self.condition_id}, updated_at={self.updated_at})>"
        )

    @classmethod
    def count_nfts_by_prefix(cls, session, prefix: str) -> int:
        """Get the count of NFTs with the specified prefix."""
        stmt = select(func.count()).where(cls.prefix == prefix)
        return session.scalar(stmt)
    
    @classmethod
    def get_by_prefix(cls, session, prefix: str) -> list["NFT"]:
        """Get all NFTs with the specified prefix."""
        stmt = select(cls).where(cls.prefix == prefix)
        return session.scalars(stmt).all()