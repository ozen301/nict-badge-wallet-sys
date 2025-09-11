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
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT


class BlockchainTransaction(Base):
    """On-chain action associated with an NFT or user.

    Stores request and response payloads for blockchain operations such as
    minting or transferring NFTs.
    """

    __tablename__ = "blockchain_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Changed from user_id (FK to users.id) to user_paymail (FK to users.paymail)
    user_paymail: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.paymail", ondelete="SET NULL"), nullable=True
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="User.paymail==BlockchainTransaction.user_paymail",
        back_populates="chain_txs",
    )
    nft: Mapped[Optional["NFT"]] = relationship(back_populates="chain_txs")

    __table_args__ = (
        CheckConstraint("type IN ('mint','transfer','burn')", name="type_enum"),
        CheckConstraint(
            "status IN ('queued','sent','confirmed','failed')", name="status_enum"
        ),
        Index("ix_chain_nft", "nft_id"),
        Index("ix_chain_status", "status"),
        Index("ix_chain_type_status", "type", "status"),
        Index("ix_chain_user_paymail", "user_paymail"),
    )

    def __repr__(self) -> str:
        return (
            f"<BlockchainTransaction(id={self.id}, user_paymail={self.user_paymail}, "
            f"nft_id={self.nft_id}, status='{self.status}', created_at={self.created_at})>"
        )
