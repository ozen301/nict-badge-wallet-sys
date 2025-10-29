from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ..db.utils import dt_iso
from .base import Base

if TYPE_CHECKING:
    from .nft import NFT
    from .ownership import UserNFTOwnership
    from .user import User


class CouponTemplate(Base):
    """Defines a coupon template, including naming, supply and expiry defaults."""

    __tablename__ = "coupon_templates"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    prefix: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_serial: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expiry_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Optional default expiry window in days
    store_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Optional store label for app display
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    bindings: Mapped[list["NFTCouponBinding"]] = relationship(
        "NFTCouponBinding",
        back_populates="template",
        cascade="all, delete-orphan",
    )
    instances: Mapped[list["CouponInstance"]] = relationship(
        "CouponInstance",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            "<CouponTemplate("
            f"id={self.id}, prefix='{self.prefix}', active={self.active}, "
            f"next_serial={self.next_serial}, max_supply={self.max_supply}"
            ")>"
        )

    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["CouponTemplate"]:
        """Fetch a template by its unique prefix."""

        return session.scalar(select(cls).where(cls.prefix == prefix))

    @classmethod
    def get_active(cls, session: Session) -> list["CouponTemplate"]:
        """Return all templates flagged as active ordered by creation."""

        stmt = select(cls).where(cls.active.is_(True)).order_by(cls.id)
        return list(session.scalars(stmt))

    @property
    def remaining_supply(self) -> Optional[int]:
        """Remaining coupons available under the template's supply cap."""

        if self.max_supply is None:
            return None
        return max(self.max_supply - (self.next_serial - 1), 0)


class NFTCouponBinding(Base):
    """Links an NFT to a coupon template with issuance rules."""

    __tablename__ = "nft_coupon_bindings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    nft_id: Mapped[int] = mapped_column(ForeignKey("nfts.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("coupon_templates.id"), nullable=False
    )
    quantity_per_claim: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    template: Mapped["CouponTemplate"] = relationship(back_populates="bindings")
    nft: Mapped["NFT"] = relationship(back_populates="coupon_bindings")

    def __repr__(self) -> str:
        return (
            "<NFTCouponBinding("
            f"id={self.id}, nft_id={self.nft_id}, template_id={self.template_id}, "
            f"quantity_per_claim={self.quantity_per_claim}, active={self.active}"
            ")>"
        )

    @classmethod
    def get_active_for_nft(
        cls, session: Session, nft_id: int
    ) -> list["NFTCouponBinding"]:
        """Return active bindings for a given NFT."""

        stmt = (
            select(cls)
            .where(cls.nft_id == nft_id, cls.active.is_(True))
            .order_by(cls.id)
        )
        return list(session.scalars(stmt))

    @classmethod
    def get_binding(
        cls, session: Session, nft_id: int, template_id: int
    ) -> Optional["NFTCouponBinding"]:
        """Fetch a specific NFT-to-template binding."""

        stmt = select(cls).where(
            cls.nft_id == nft_id,
            cls.template_id == template_id,
        )
        return session.scalar(stmt)


class CouponInstance(Base):
    """Represents an issued coupon tied to an NFT and optionally a user."""

    __tablename__ = "coupon_instances"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("coupon_templates.id"), nullable=False
    )
    nft_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nfts.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    ownership_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_nft_ownership.id"), nullable=True
    )
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Store label propagated from template when issued

    # Relationships
    template: Mapped["CouponTemplate"] = relationship(back_populates="instances")
    nft: Mapped[Optional["NFT"]] = relationship(back_populates="coupon_instances")
    user: Mapped[Optional["User"]] = relationship(back_populates="coupons")
    ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        back_populates="coupon_instances"
    )

    def __repr__(self) -> str:
        return (
            "<CouponInstance("
            f"id={self.id}, code='{self.coupon_code}', template_id={self.template_id}, "
            f"user_id={self.user_id}, redeemed={self.redeemed}, expiry={dt_iso(self.expiry)}"
            ")>"
        )

    @classmethod
    def get_by_coupon_code(
        cls, session: Session, coupon_code: str
    ) -> Optional["CouponInstance"]:
        """Retrieve a coupon instance by its unique code."""

        return session.scalar(select(cls).where(cls.coupon_code == coupon_code))

    @classmethod
    def get_unredeemed_for_user(
        cls, session: Session, user_id: int
    ) -> list["CouponInstance"]:
        """List a user's unredeemed coupons, most recent first."""

        stmt = (
            select(cls)
            .where(cls.user_id == user_id, cls.redeemed.is_(False))
            .order_by(cls.assigned_at.desc())
        )
        return list(session.scalars(stmt))

    def mark_redeemed(self, *, timestamp: Optional[datetime] = None) -> None:
        """Mark the coupon as redeemed and set the redemption timestamp."""

        if self.redeemed:
            return
        self.redeemed = True
        self.redeemed_at = timestamp or datetime.now(timezone.utc)

    def is_expired(self, *, reference_time: Optional[datetime] = None) -> bool:
        """Check if the coupon has expired relative to ``reference_time``."""

        if self.expiry is None:
            return False
        ref = reference_time or datetime.now(timezone.utc)
        return self.expiry <= ref
