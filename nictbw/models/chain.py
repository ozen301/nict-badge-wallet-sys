from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
)
from . import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT

class BlockchainTransaction(Base):
    __tablename__ = "blockchain_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL"), nullable=True
    )
    unique_nft_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    request_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[Optional["User"]] = relationship(back_populates="chain_txs")
    nft: Mapped[Optional["NFT"]] = relationship(back_populates="chain_txs")

    __table_args__ = (
        CheckConstraint("type IN ('mint','transfer','burn')", name="type_enum"),
        CheckConstraint(
            "status IN ('queued','sent','confirmed','failed')", name="status_enum"
        ),
        Index("ix_chain_nft", "nft_id"),
        Index("ix_chain_status", "status"),
        Index("ix_chain_type_status", "type", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<BlockchainTransaction(id={self.id}, user_id={self.user_id}, "
            f"nft_id={self.nft_id}, status='{self.status}', created_at={self.created_at})>"
        )
