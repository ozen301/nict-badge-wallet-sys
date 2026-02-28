from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    func,
    select,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ..db.utils import dt_iso
from .base import Base
from .id_type import ID_TYPE
from .utils import generate_unique_nft_id

if TYPE_CHECKING:
    from .ownership import NFTInstance
    from .user import User


class NFTCondition(Base):
    """Constraints that govern when an NFT can be issued or claimed."""

    __tablename__ = "nft_conditions"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    radius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    required_definition_id: Mapped[Optional[int]] = mapped_column(
        "required_nft_id", BigInteger, nullable=True
    )
    prohibited_definition_id: Mapped[Optional[int]] = mapped_column(
        "prohibited_nft_id", BigInteger, nullable=True
    )
    other_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class NFTDefinition(Base):
    """NFT definition model (acts as template data in current API schema)."""

    __tablename__ = "nfts"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    template_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("nft_templates.id"), nullable=True, index=True
    )
    prefix: Mapped[str] = mapped_column(String(100), nullable=False)
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    nft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promotional_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    store_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    local_image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qr_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("nft_conditions.id"), nullable=True
    )
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minted_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    triggers_bingo_card: Mapped[bool] = mapped_column(Boolean, default=False)
    distributes_coupons: Mapped[bool] = mapped_column(Boolean, default=True)
    bingo_period_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("bingo_periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bingo_is_center: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    bingo_force_include: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_dummy: Mapped[bool] = mapped_column(Boolean, default=False)
    can_be_center: Mapped[bool] = mapped_column(Boolean, default=True)
    bingo_random_candidate: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    allow_bingo_duplicates: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    bingo_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_by_admin_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("prefix", name="nfts_prefix_key"),
    )

    prize_draw_results = relationship("PrizeDrawResult", back_populates="definition")
    ownerships = relationship("NFTInstance", back_populates="definition")
    template = relationship("NFTTemplate")
    bingo_period = relationship("BingoPeriod")

    @property
    def remaining_supply(self) -> Optional[int]:
        if self.max_supply is None:
            return None
        return max(0, self.max_supply - self.minted_count)

    def to_json(self, *, compact: bool = False) -> dict:
        full = {
            "id": self.id,
            "prefix": self.prefix,
            "shared_key": self.shared_key,
            "name": self.name,
            "nft_type": self.nft_type,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "promotional_text": self.promotional_text,
            "store_url": self.store_url,
            "image_url": self.image_url,
            "qr_image_url": self.qr_image_url,
            "max_supply": self.max_supply,
            "minted_count": self.minted_count,
            "status": self.status,
            "triggers_bingo_card": self.triggers_bingo_card,
            "distributes_coupons": self.distributes_coupons,
            "is_dummy": self.is_dummy,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "created_at": dt_iso(self.created_at),
            "updated_at": dt_iso(self.updated_at),
        }
        if not compact:
            return full
        keep = {
            "id",
            "prefix",
            "name",
            "image_url",
            "triggers_bingo_card",
            "latitude",
            "longitude",
            "promotional_text",
            "is_dummy",
        }
        return {k: v for k, v in full.items() if k in keep}

    @classmethod
    def count_instances_by_prefix(cls, session: Session, prefix: str) -> int:
        """Count ownership records for NFTs sharing the given prefix."""

        from .ownership import NFTInstance

        stmt = (
            select(func.count())
            .select_from(NFTInstance)
            .join(cls, cls.id == NFTInstance.definition_id)
            .where(cls.prefix == prefix)
        )
        return int(session.scalar(stmt) or 0)

    def issue_dbwise_to_user(
        self,
        session: Session,
        user: "User",
        *,
        unique_nft_id: Optional[str] = None,
        serial_number: Optional[int] = None,
        acquired_at: Optional[datetime] = None,
        status: str = "succeeded",
        **ownership_fields,
    ) -> "NFTInstance":
        """Assign ownership of this NFT definition to a user in the database."""

        from .ownership import NFTInstance

        if self.max_supply is not None and self.minted_count >= self.max_supply:
            raise ValueError("Max supply for this NFT definition has been reached")

        existing = NFTInstance.get_by_user_and_definition(session, user, self)
        if existing is not None:
            raise ValueError("User already owns this NFT definition")

        if not inspect(self).persistent:
            session.add(self)
            session.flush()

        if serial_number is None:
            serial_number = self.minted_count
        if unique_nft_id is None:
            unique_nft_id = generate_unique_nft_id(self.prefix, session=session)

        ownership = NFTInstance(
            user=user,
            definition=self,
            serial_number=serial_number,
            unique_nft_id=unique_nft_id,
            acquired_at=acquired_at or datetime.now(timezone.utc),
            status=status,
            **ownership_fields,
        )
        session.add(ownership)
        self.minted_count += 1

        if hasattr(user, "ownerships"):
            try:
                user.unlock_bingo_cells(session, ownership)
            except Exception:
                pass

        session.flush()
        return ownership


class NFTTemplate(Base):
    """Reusable NFT template metadata (currently unused by API)."""

    __tablename__ = "nft_templates"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qr_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    default_condition_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("nft_conditions.id"), nullable=True
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    radius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    required_definition_id: Mapped[Optional[int]] = mapped_column(
        "required_nft_id", BigInteger, nullable=True
    )
    prohibited_definition_id: Mapped[Optional[int]] = mapped_column(
        "prohibited_nft_id", BigInteger, nullable=True
    )
    other_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggers_bingo_card: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_by_admin_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("prefix", name="nft_templates_prefix_key"),
    )

    def instantiate_nft(
        self,
        session: Session,
        user: "User",
        *,
        shared_key: str,
        override_name: Optional[str] = None,
        override_description: Optional[str] = None,
        override_created_by_admin_id: Optional[int] = None,
        unique_nft_id: Optional[str] = None,
        serial_number: Optional[int] = None,
        acquired_at: Optional[datetime] = None,
        status: str = "succeeded",
        **ownership_fields,
    ) -> "NFTInstance":
        """Instantiate an NFT instance from this template for ``user``.

        The method reuses an existing definition row for this template when
        available; otherwise it creates one and then issues an instance.
        """

        from .ownership import NFTInstance

        definition = session.scalar(
            select(NFTDefinition).where(
                (NFTDefinition.template_id == self.id) | (NFTDefinition.prefix == self.prefix)
            )
        )
        if definition is None:
            definition = NFTDefinition(
                template_id=self.id,
                prefix=self.prefix,
                shared_key=shared_key,
                name=override_name or self.name,
                nft_type="default",
                category=self.category,
                subcategory=self.subcategory,
                description=override_description or self.description,
                image_url=self.image_url,
                condition_id=self.default_condition_id,
                max_supply=self.max_supply,
                status=self.status,
                triggers_bingo_card=self.triggers_bingo_card,
                created_by_admin_id=override_created_by_admin_id or self.created_by_admin_id,
            )
            session.add(definition)
            session.flush()

        instance: NFTInstance = definition.issue_dbwise_to_user(
            session,
            user,
            unique_nft_id=unique_nft_id,
            serial_number=serial_number,
            acquired_at=acquired_at,
            status=status,
            **ownership_fields,
        )
        return instance

    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["NFTTemplate"]:
        stmt = select(cls).where(cls.prefix == prefix)
        return session.scalar(stmt)

    @classmethod
    def get_by_name(cls, session: Session, name: str) -> Optional["NFTTemplate"]:
        stmt = select(cls).where(cls.name == name)
        return session.scalar(stmt)
