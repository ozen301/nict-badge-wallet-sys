from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
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
    def __init__(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location_range: Optional[str] = None,
        required_nft_id: Optional[int] = None,
        prohibited_nft_id: Optional[int] = None,
        other_conditions: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.location_range = location_range
        self.required_nft_id = required_nft_id
        self.prohibited_nft_id = prohibited_nft_id
        self.other_conditions = other_conditions
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

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
    def __init__(
        self,
        prefix: str,
        shared_key: str,
        name: str,
        nft_type: str,
        id_on_chain: Optional[int] = None,
        origin: Optional[str] = None,
        current_location: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        condition_id: Optional[int] = None,
        max_supply: Optional[int] = None,
        minted_count: int = 0,
        status: str = "active",
        created_by_admin_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.prefix = prefix
        self.shared_key = shared_key
        self.name = name
        self.nft_type = nft_type
        self.id_on_chain = id_on_chain
        self.origin = origin
        self.current_location = current_location
        self.description = description
        self.image_url = image_url
        self.condition_id = condition_id
        self.max_supply = max_supply
        self.minted_count = minted_count
        self.status = status
        if created_by_admin_id is not None:
            self.created_by_admin_id = created_by_admin_id
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "nfts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    nft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_on_chain: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    current_location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nft_conditions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
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
    condition: Mapped[Optional[NFTCondition]] = relationship(
        foreign_keys=[condition_id]
    )
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
    def count_nfts_by_prefix(cls, session: Session, prefix: str) -> int:
        """Get the count of NFTs with the specified prefix."""
        stmt = select(func.count()).where(cls.prefix == prefix)
        res = session.scalar(stmt)
        return res or 0

    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["NFT"]:
        """Get the first NFT with the specified prefix."""
        stmt = select(cls).where(cls.prefix == prefix)
        return session.scalar(stmt)

    def count_same_prefix_nfts(self, session: Session) -> int:
        """Get the count of NFTs with the same prefix as this NFT."""
        return NFT.count_nfts_by_prefix(session, self.prefix)
