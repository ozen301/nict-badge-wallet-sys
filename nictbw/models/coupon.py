from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, object_session, relationship

from ..db.utils import dt_iso
from .base import Base
from .id_type import ID_TYPE

if TYPE_CHECKING:
    from .nft import NFTDefinition
    from .ownership import NFTInstance
    from .user import User


class CouponTemplate(Base):
    """Defines a coupon template, including naming, supply and expiry defaults."""

    __tablename__ = "coupon_templates"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_serial: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_per_user: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default=text("1")
    )
    eligible_for_cross_promo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    max_redeem: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expiry_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    available_stores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    default_display_nft_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE,
        ForeignKey("nfts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixed_expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("prefix", name="coupon_templates_prefix_key"),
    )

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

    @property
    def redeemed_count(self) -> int:
        session = object_session(self)
        if session is None:
            return sum(1 for instance in self.instances if instance.redeemed)
        stmt = (
            select(func.count())
            .select_from(CouponInstance)
            .where(
                CouponInstance.template_id == self.id,
                CouponInstance.redeemed.is_(True),
            )
        )
        result = session.scalar(stmt)
        return int(result or 0)

    @property
    def remaining_redeem(self) -> Optional[int]:
        if self.max_redeem is None:
            return None
        return max(self.max_redeem - self.redeemed_count, 0)

    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["CouponTemplate"]:
        return session.scalar(select(cls).where(cls.prefix == prefix))

    @classmethod
    def get_active(cls, session: Session) -> list["CouponTemplate"]:
        stmt = select(cls).where(cls.active.is_(True)).order_by(cls.id)
        return list(session.scalars(stmt))


class NFTCouponBinding(Base):
    """Links an NFTDefinition to a coupon template with issuance rules."""

    __tablename__ = "nft_coupon_bindings"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    definition_id: Mapped[int] = mapped_column(
        "nft_id", ID_TYPE, ForeignKey("nfts.id"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("coupon_templates.id"), nullable=False
    )
    quantity_per_claim: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    template: Mapped["CouponTemplate"] = relationship(back_populates="bindings")
    definition: Mapped["NFTDefinition"] = relationship()

    @classmethod
    def get_active_for_nft(
        cls, session: Session, definition_id: int
    ) -> list["NFTCouponBinding"]:
        stmt = (
            select(cls)
            .where(cls.definition_id == definition_id, cls.active.is_(True))
            .order_by(cls.id)
        )
        return list(session.scalars(stmt))

    @classmethod
    def get_binding(
        cls, session: Session, definition_id: int, template_id: int
    ) -> Optional["NFTCouponBinding"]:
        stmt = select(cls).where(
            cls.definition_id == definition_id,
            cls.template_id == template_id,
        )
        return session.scalar(stmt)


class CouponInstance(Base):
    """Represents an issued coupon tied to an NFTDefinition and optionally a user."""

    __tablename__ = "coupon_instances"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    template_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("coupon_templates.id"), nullable=False
    )
    definition_id: Mapped[Optional[int]] = mapped_column(
        "nft_id", ID_TYPE, ForeignKey("nfts.id"), nullable=True
    )
    display_definition_id: Mapped[Optional[int]] = mapped_column(
        "display_nft_id",
        ID_TYPE,
        ForeignKey("nfts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("users.id"), nullable=True
    )
    ownership_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("user_nft_ownership.id"), nullable=True
    )
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_code: Mapped[str] = mapped_column(String(128), nullable=False)
    usage_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    usage_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    redeem_request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    redeem_client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    redeem_x_forwarded_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redeem_user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    available_stores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    player_usage_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    template: Mapped["CouponTemplate"] = relationship(back_populates="instances")
    definition: Mapped[Optional["NFTDefinition"]] = relationship(
        "NFTDefinition", foreign_keys=[definition_id]
    )
    display_definition: Mapped[Optional["NFTDefinition"]] = relationship(
        "NFTDefinition", foreign_keys=[display_definition_id]
    )
    user: Mapped[Optional["User"]] = relationship(back_populates="coupons")
    ownership: Mapped[Optional["NFTInstance"]] = relationship(
        back_populates="coupon_instances"
    )

    __table_args__ = (
        UniqueConstraint("coupon_code", name="coupon_instances_coupon_code_key"),
    )

    @classmethod
    def get_by_coupon_code(
        cls, session: Session, coupon_code: str
    ) -> Optional["CouponInstance"]:
        return session.scalar(select(cls).where(cls.coupon_code == coupon_code))

    @classmethod
    def get_unredeemed_for_user(
        cls, session: Session, user_id: int
    ) -> list["CouponInstance"]:
        stmt = (
            select(cls)
            .where(cls.user_id == user_id, cls.redeemed.is_(False))
            .order_by(cls.assigned_at.desc())
        )
        return list(session.scalars(stmt))

    def mark_redeemed(self, *, timestamp: Optional[datetime] = None) -> None:
        if self.redeemed:
            return
        self.redeemed = True
        self.redeemed_at = timestamp or datetime.now(timezone.utc)

    def is_expired(self, *, reference_time: Optional[datetime] = None) -> bool:
        if self.expiry is None:
            return False
        ref = reference_time or datetime.now(timezone.utc)
        return self.expiry < ref

    def __repr__(self) -> str:
        return (
            "<CouponInstance("
            f"id={self.id}, code='{self.coupon_code}', template_id={self.template_id}, "
            f"user_id={self.user_id}, redeemed={self.redeemed}, expiry={dt_iso(self.expiry)}"
            ")>"
        )


class CouponStore(Base):
    """Store pool for dynamic player coupon allocation."""

    __tablename__ = "coupon_stores"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nft_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    usage_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_stores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    store_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    nft: Mapped["NFTDefinition"] = relationship()

    __table_args__ = (
        UniqueConstraint("name", name="uq_coupon_stores_name"),
        Index("ix_coupon_stores_active", "active"),
    )

    @property
    def condition_text(self) -> Optional[str]:
        return self.usage_restrictions


class CouponPlayer(Base):
    """Player profile for dynamic player coupon allocation."""

    __tablename__ = "coupon_players"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    jersey_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name_ja: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    positions: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    template_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("coupon_templates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    template: Mapped["CouponTemplate"] = relationship()

    __table_args__ = (
        UniqueConstraint("jersey_number", name="uq_coupon_players_jersey"),
        Index("ix_coupon_players_active", "active"),
    )


class CouponPlayerStoreInventory(Base):
    """Inventory/quota for postcard prizes per (store, player) pair."""

    __tablename__ = "coupon_player_store_inventories"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    store_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("coupon_stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("coupon_players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    issued_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    max_redeem: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    redeemed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=text("now()"),
        default=lambda: datetime.now(timezone.utc),
    )

    store: Mapped["CouponStore"] = relationship()
    player: Mapped["CouponPlayer"] = relationship()

    __table_args__ = (
        UniqueConstraint("store_id", "player_id", name="uq_coupon_player_store"),
        CheckConstraint("max_supply IS NULL OR max_supply >= 0", name="ck_cpsi_max_supply_nonneg"),
        CheckConstraint("issued_count >= 0", name="ck_cpsi_issued_count_nonneg"),
        CheckConstraint("max_redeem IS NULL OR max_redeem >= 0", name="ck_cpsi_max_redeem_nonneg"),
        CheckConstraint("redeemed_count >= 0", name="ck_cpsi_redeemed_count_nonneg"),
        CheckConstraint(
            "max_supply IS NULL OR max_redeem IS NULL OR max_redeem <= max_supply",
            name="ck_cpsi_max_redeem_le_max_supply",
        ),
        Index("ix_cpsi_active", "active"),
    )
