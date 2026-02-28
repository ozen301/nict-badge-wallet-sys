from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .id_type import ID_TYPE

if TYPE_CHECKING:
    from .user import User
    from .nft import NFTDefinition
    from .coupon import CouponInstance
    from .prize_draw import PrizeDrawResult, RaffleEntry


class NFTInstance(Base):
    """Association table recording which user owns which NFT definition."""

    __tablename__ = "user_nft_ownership"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id"), nullable=False)
    definition_id: Mapped[int] = mapped_column(
        "nft_id", ID_TYPE, ForeignKey("nfts.id"), nullable=False
    )
    bingo_period_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("bingo_periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_instance_id: Mapped[str] = mapped_column(
        "unique_nft_id", String(255), nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded")
    blockchain_nft_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    nft_origin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_nft_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    blockchain_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sub_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    blockchain_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    blockchain_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nft_id_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_claim_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    other_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ownerships")
    definition: Mapped["NFTDefinition"] = relationship(back_populates="ownerships")
    prize_draw_results: Mapped[list["PrizeDrawResult"]] = relationship(
        "PrizeDrawResult",
        back_populates="ownership",
    )
    raffle_entries: Mapped[list["RaffleEntry"]] = relationship(
        "RaffleEntry",
        back_populates="ownership",
    )
    coupon_instances: Mapped[list["CouponInstance"]] = relationship(
        "CouponInstance",
        back_populates="ownership",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "nft_id", name="uq_user_nft_once"),
    )

    @classmethod
    def get_by_user_and_definition(
        cls,
        session,
        user: "User | int",
        definition: "NFTDefinition | int",
    ) -> Optional["NFTInstance"]:
        """Retrieve ownership record linking ``user`` to ``definition``."""

        def _to_id(obj: "int | User | NFTDefinition") -> int:
            return obj if isinstance(obj, int) else obj.id

        user_id = _to_id(user)
        definition_id = _to_id(definition)
        return session.query(cls).filter(
            cls.user_id == user_id, cls.definition_id == definition_id
        ).one_or_none()
