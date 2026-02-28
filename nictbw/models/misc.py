from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    BigInteger,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .id_type import ID_TYPE


class NFTClaimRequest(Base):
    """Tracks asynchronous NFT claim progress."""

    __tablename__ = "nft_claim_requests"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    tmp_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    definition_id: Mapped[int] = mapped_column(
        "nft_id",
        ID_TYPE, ForeignKey("nfts.id"), nullable=False, index=True
    )
    prefix: Mapped[str] = mapped_column(String(100), nullable=False)
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instance_id: Mapped[Optional[int]] = mapped_column(
        "ownership_id",
        ID_TYPE, ForeignKey("user_nft_ownership.id"), nullable=True
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bingo_line_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    coupon_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    coupon_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coupon_next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    coupon_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_x_forwarded_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User")
    definition = relationship("NFTDefinition")
    instance = relationship("NFTInstance", foreign_keys=[instance_id])

    __table_args__ = (
        UniqueConstraint("tmp_id", name="uq_nft_claim_tmp_id"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_nft_claim_idempotency"),
        Index("ix_nft_claim_user_status", "user_id", "status"),
        Index("ix_nft_claim_created", "created_at"),
    )


class UserActivityEvent(Base):
    """Append-only audit/event log for user/admin/system actions."""

    __tablename__ = "user_activity_events"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_admin_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(ID_TYPE, nullable=True, index=True)
    resource_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    http_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    x_forwarded_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    succeeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    actor_user = relationship("User", foreign_keys=[actor_user_id])
    actor_admin = relationship("Admin", foreign_keys=[actor_admin_id])


class ExternalAccount(Base):
    """External OAuth account linkage."""

    __tablename__ = "external_accounts"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AppBanner(Base):
    """In-app banner notifications."""

    __tablename__ = "app_banners"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    type: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_uids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PreMintedUser(Base):
    """Pre-registered user pool for async registration."""

    __tablename__ = "pre_minted_users"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    on_chain_id: Mapped[str] = mapped_column(String(255), nullable=False)
    paymail: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("on_chain_id", name="pre_minted_users_on_chain_id_key"),
        UniqueConstraint("paymail", name="pre_minted_users_paymail_key"),
    )


class SystemConfiguration(Base):
    """System-wide configuration settings."""

    __tablename__ = "system_configurations"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
