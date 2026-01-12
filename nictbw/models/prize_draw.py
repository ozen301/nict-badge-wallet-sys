"""Database models for the prize draw subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    Float,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
    text,
    select,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from .base import Base
from .id_type import ID_TYPE

if TYPE_CHECKING:
    from .bingo import BingoCard
    from .user import User
    from .nft import NFT
    from .ownership import UserNFTOwnership


class PrizeDrawType(Base):
    """Defines a distinct configuration for evaluating prize draws."""

    __tablename__ = "prize_draw_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    """Primary key."""

    internal_name: Mapped[str] = mapped_column(String(100), nullable=False)
    """Machine friendly identifier used by application code."""

    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """Optional human readable label shown to admins."""

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Free form documentation about how this draw type behaves."""

    algorithm_key: Mapped[str] = mapped_column(String(100), nullable=False)
    """Identifier for the scoring algorithm to use when running draws."""

    default_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    """Minimum similarity threshold applied when a draw does not supply one."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    """Timestamp when the draw type was created."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    """Timestamp automatically bumped when the draw type is modified."""

    winning_numbers: Mapped[list["PrizeDrawWinningNumber"]] = relationship(
        back_populates="draw_type",
        cascade="all, delete-orphan",
    )
    """Collection of winning numbers recorded for this draw type."""

    results: Mapped[list["PrizeDrawResult"]] = relationship(
        back_populates="draw_type",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["RaffleEvent"]] = relationship(back_populates="draw_type")
    """All evaluation results belonging to this draw type."""

    __table_args__ = (
        UniqueConstraint("internal_name", name="prize_draw_types_internal_name_key"),
    )

    def latest_winning_number(
        self, session: Session
    ) -> Optional["PrizeDrawWinningNumber"]:
        """Return the most recently stored winning number for this draw type."""

        stmt = (
            select(PrizeDrawWinningNumber)
            .where(PrizeDrawWinningNumber.draw_type_id == self.id)
            .order_by(
                PrizeDrawWinningNumber.created_at.desc(),
                PrizeDrawWinningNumber.id.desc(),
            )
        )
        return session.scalars(stmt).first()

    def __init__(
        self,
        *,
        internal_name: str,
        algorithm_key: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        default_threshold: Optional[float] = None,
        winning_numbers: Optional[list["PrizeDrawWinningNumber"]] = None,
        results: Optional[list["PrizeDrawResult"]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        self.internal_name = internal_name
        self.algorithm_key = algorithm_key
        self.display_name = display_name
        self.description = description
        self.default_threshold = default_threshold
        if winning_numbers is not None:
            self.winning_numbers = winning_numbers
        if results is not None:
            self.results = results
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    def __repr__(self) -> str:  # pragma: no cover - repr is trivial
        return "<PrizeDrawType(id={id}, internal_name={name}, algorithm_key={algo})>".format(
            id=self.id,
            name=self.internal_name,
            algo=self.algorithm_key,
        )

    @classmethod
    def get_by_internal_name(
        cls, session: Session, internal_name: str
    ) -> Optional["PrizeDrawType"]:
        """Return the draw type matching ``internal_name`` if it exists."""

        return session.scalar(select(cls).where(cls.internal_name == internal_name))


class PrizeDrawWinningNumber(Base):
    """Stores an externally supplied winning number for a draw type."""

    __tablename__ = "prize_draw_winning_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    """Primary key."""

    draw_type_id: Mapped[int] = mapped_column(
        ForeignKey("prize_draw_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """Foreign key referencing :class:`PrizeDrawType`."""

    value: Mapped[str] = mapped_column(String(255), nullable=False)
    """Winning number supplied by the external system."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    """Timestamp recording when the winning number was stored."""

    draw_type: Mapped["PrizeDrawType"] = relationship(back_populates="winning_numbers")
    """Relationship back to the owning draw type."""

    results: Mapped[list["PrizeDrawResult"]] = relationship(
        back_populates="winning_number"
    )
    events: Mapped[list["RaffleEvent"]] = relationship(back_populates="winning_number")


class RaffleEvent(Base):
    __tablename__ = "raffle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("prize_draw_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    winning_number_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("prize_draw_winning_numbers.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_by_admin_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    winner_user_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    winner_result_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("prize_draw_results.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    draw_type: Mapped["PrizeDrawType"] = relationship(back_populates="events")
    winning_number: Mapped[Optional["PrizeDrawWinningNumber"]] = relationship(
        back_populates="events"
    )
    winner_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="raffle_events_won", foreign_keys=[winner_user_id]
    )
    winner_result: Mapped[Optional["PrizeDrawResult"]] = relationship(
        "PrizeDrawResult", foreign_keys=[winner_result_id], post_update=True
    )
    entries: Mapped[list["RaffleEntry"]] = relationship(
        "RaffleEntry", back_populates="raffle_event"
    )
    results: Mapped[list["PrizeDrawResult"]] = relationship(
        "PrizeDrawResult",
        back_populates="event",
        foreign_keys="PrizeDrawResult.event_id",
    )


class RaffleEntry(Base):
    __tablename__ = "raffle_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bingo_card_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("bingo_cards.id", ondelete="SET NULL"), nullable=True
    )
    ownership_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    raffle_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("raffle_events.id", ondelete="SET NULL"), nullable=True
    )
    line_signature: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="raffle_entries")
    bingo_card: Mapped[Optional["BingoCard"]] = relationship(
        "BingoCard", back_populates="raffle_entries"
    )
    ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        "UserNFTOwnership", back_populates="raffle_entries"
    )
    raffle_event: Mapped[Optional["RaffleEvent"]] = relationship(
        "RaffleEvent", back_populates="entries"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "bingo_card_id", name="uq_raffle_entry_per_card"),
    )
    """All prize draw results evaluated using this winning number."""

    def __init__(
        self,
        *,
        value: str,
        draw_type: Optional["PrizeDrawType"] = None,
        draw_type_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        results: Optional[list["PrizeDrawResult"]] = None,
    ) -> None:
        self.value = value
        if draw_type is not None:
            self.draw_type = draw_type
        if draw_type_id is not None:
            self.draw_type_id = draw_type_id
        if created_at is not None:
            self.created_at = created_at
        if results is not None:
            self.results = results

    def __repr__(self) -> str:  # pragma: no cover - repr is trivial
        return "<PrizeDrawWinningNumber(id={id}, draw_type_id={dt}, value={value})>".format(
            id=self.id,
            dt=self.draw_type_id,
            value=self.value,
        )


class PrizeDrawResult(Base):
    """Immutable record of evaluating an NFT for a given draw."""

    __tablename__ = "prize_draw_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    """Surrogate primary key."""

    event_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("raffle_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    draw_type_id: Mapped[int] = mapped_column(
        ForeignKey("prize_draw_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """Draw type used for this evaluation."""

    winning_number_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("prize_draw_winning_numbers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """Specific winning number applied to this evaluation, if recorded."""

    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    """User who owned the NFT at evaluation time."""

    nft_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    """NFT evaluated during the draw."""

    ownership_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    """Snapshot of the ownership record to preserve historical association."""

    draw_number: Mapped[str] = mapped_column(String(255), nullable=False)
    """Draw number derived from the NFT origin."""

    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    """Computed similarity score (0.0-1.0) comparing the draw number to the winning number."""

    draw_top_digits: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    """Top 10 significant digits (string) of the hashed draw number for user display."""

    winning_top_digits: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    """Top 10 significant digits (string) of the hashed winning number for user display."""

    threshold_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    """Threshold that was applied when computing the outcome."""

    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    """Outcome derived from the evaluation ("win", "lose", or "pending")."""

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    """Timestamp when the draw was evaluated."""

    event: Mapped[Optional["RaffleEvent"]] = relationship(
        "RaffleEvent", back_populates="results", foreign_keys=[event_id]
    )
    draw_type: Mapped["PrizeDrawType"] = relationship(back_populates="results")
    """Relationship to the draw type."""

    winning_number: Mapped[Optional["PrizeDrawWinningNumber"]] = relationship(
        back_populates="results"
    )
    """Relationship to the winning number used, if any."""

    user: Mapped["User"] = relationship(back_populates="prize_draw_results")
    """Relationship to the user evaluated."""

    nft: Mapped["NFT"] = relationship(back_populates="prize_draw_results")
    """Relationship to the NFT evaluated."""

    ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        back_populates="prize_draw_results"
    )
    """Relationship to the ownership snapshot for historical tracking."""

    __table_args__ = (
        UniqueConstraint("nft_id", "draw_type_id", name="uq_prize_draw_result_unique"),
        Index("ix_prize_draw_results_outcome", "outcome"),
    )

    def __init__(
        self,
        *,
        event: Optional["RaffleEvent"] = None,
        event_id: Optional[int] = None,
        draw_type: Optional["PrizeDrawType"] = None,
        draw_type_id: Optional[int] = None,
        winning_number: Optional["PrizeDrawWinningNumber"] = None,
        winning_number_id: Optional[int] = None,
        user: Optional["User"] = None,
        user_id: Optional[int] = None,
        nft: Optional["NFT"] = None,
        nft_id: Optional[int] = None,
        ownership: Optional["UserNFTOwnership"] = None,
        ownership_id: Optional[int] = None,
        draw_number: str,
        similarity_score: Optional[float] = None,
        draw_top_digits: Optional[str] = None,
        winning_top_digits: Optional[str] = None,
        threshold_used: Optional[float] = None,
        outcome: str = "pending",
        evaluated_at: Optional[datetime] = None,
    ) -> None:
        if event is not None:
            self.event = event
        if event_id is not None:
            self.event_id = event_id
        if draw_type is not None:
            self.draw_type = draw_type
        if draw_type_id is not None:
            self.draw_type_id = draw_type_id
        if winning_number is not None:
            self.winning_number = winning_number
        if winning_number_id is not None:
            self.winning_number_id = winning_number_id
        if user is not None:
            self.user = user
        if user_id is not None:
            self.user_id = user_id
        if nft is not None:
            self.nft = nft
        if nft_id is not None:
            self.nft_id = nft_id
        if ownership is not None:
            self.ownership = ownership
        if ownership_id is not None:
            self.ownership_id = ownership_id
        self.draw_number = draw_number
        self.similarity_score = similarity_score
        self.draw_top_digits = draw_top_digits
        self.winning_top_digits = winning_top_digits
        self.threshold_used = threshold_used
        self.outcome = outcome
        if evaluated_at is not None:
            self.evaluated_at = evaluated_at

    def __repr__(self) -> str:  # pragma: no cover - repr is trivial
        return "<PrizeDrawResult(id={id}, draw_type_id={dt}, nft_id={nft}, user_id={user_id}, similarity_score={similarity_score}, outcome={outcome})>".format(
            id=self.id,
            dt=self.draw_type_id,
            nft=self.nft_id,
            user_id=self.user_id,
            similarity_score=self.similarity_score,
            outcome=self.outcome,
        )


__all__ = [
    "PrizeDrawType",
    "PrizeDrawWinningNumber",
    "PrizeDrawResult",
]
