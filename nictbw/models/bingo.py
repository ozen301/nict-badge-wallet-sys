from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import TYPE_CHECKING, Iterable, Optional, Any
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy import (
    Boolean,
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    JSON,
    Text,
    select,
    text,
)
from .base import Base
from ..db.utils import dt_iso
from .id_type import ID_TYPE

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT
    from .ownership import UserNFTOwnership
    from .prize_draw import RaffleEntry


class BingoPeriod(Base):
    """Bingo season/window."""

    __tablename__ = "bingo_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cards: Mapped[list["BingoCard"]] = relationship(back_populates="period")
    rewards: Mapped[list["BingoPeriodReward"]] = relationship(back_populates="period")


class BingoPeriodReward(Base):
    """Reward NFT configuration for a bingo period."""

    __tablename__ = "bingo_period_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bingo_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reward_nft_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    period: Mapped["BingoPeriod"] = relationship(back_populates="rewards")
    reward_nft: Mapped["NFT"] = relationship("NFT")

    __table_args__ = (
        UniqueConstraint("period_id", name="uq_bingo_period_rewards_period"),
        Index("ix_bingo_period_rewards_enabled", "enabled"),
    )


class BingoCard(Base):
    """Bingo card assigned to a user.

    Represents a 3x3 grid of :class:`BingoCell` objects that can be unlocked by
    collecting NFTs matching predefined templates.
    """

    def __init__(
        self,
        user_id: int,
        issued_at: datetime,
        period_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        issuance_month: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        expiry: Optional[datetime] = None,
        state: str = "active",
        bingo_reward_claimed: bool = False,
    ):
        self.user_id = user_id
        self.issued_at = issued_at
        self.period_id = period_id
        self.start_time = start_time
        self.issuance_month = issuance_month
        self.completed_at = completed_at
        self.expiry = expiry
        self.state = state
        self.bingo_reward_claimed = bingo_reward_claimed

    __tablename__ = "bingo_cards"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bingo_periods.id"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    issuance_month: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    bingo_reward_claimed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )

    @property
    def is_expired(self) -> bool:
        if self.expiry is None:
            return False
        expiry = self.expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry < datetime.now(timezone.utc)

    user: Mapped["User"] = relationship(back_populates="bingo_cards")
    period: Mapped[Optional["BingoPeriod"]] = relationship(back_populates="cards")
    cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="card", cascade="all, delete-orphan", order_by="BingoCell.idx"
    )
    raffle_entries: Mapped[list["RaffleEntry"]] = relationship(
        "RaffleEntry", back_populates="bingo_card"
    )

    __table_args__ = (
        CheckConstraint("state IN ('active','completed','expired')", name="bingo_card_state_enum"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCard(id={self.id}, user_id={self.user_id}, "
            f"issued_at={self.issued_at}, state='{self.state}')>"
        )

    def to_json(self, *, compact: bool = False) -> dict[str, Any]:
        """Return a JSON (dict) representation of this BingoCard.

        When compact is True, return essential fields only.
        Includes all cells serialized via BingoCell.to_json(compact=compact).
        """
        cells_list: list[dict[str, Any]] = [
            c.to_json(compact=compact) for c in sorted(self.cells, key=lambda c: c.idx)
        ]

        full = {
            "id": self.id,
            "user_id": self.user_id,
            "period_id": self.period_id,
            "issued_at": dt_iso(self.issued_at),
            "start_time": dt_iso(self.start_time),
            "expiry": dt_iso(self.expiry),
            "issuance_month": self.issuance_month,
            "completed_at": dt_iso(self.completed_at),
            "state": self.state,
            "bingo_reward_claimed": self.bingo_reward_claimed,
            "cells": cells_list,
        }
        if not compact:
            return full
        keep = {
            "id",
            "state",
            "completed_at",
            "cells",
            "issuance_month",
            "bingo_reward_claimed",
            "expiry",
            "start_time",
            "period_id",
        }
        return {k: v for k, v in full.items() if k in keep}

    def to_json_str(self, *, compact: bool = False) -> str:
        """Serialize this BingoCard to a JSON string including its cells."""
        import json

        return json.dumps(self.to_json(compact=compact), ensure_ascii=False)

    @classmethod
    def generate_for_user(
        cls,
        session: Session,
        user: "User",
        center_template: "NFT",
        *,
        excluded_templates: Optional[Iterable["int | NFT"]] = None,
        included_templates: Optional[Iterable["int | NFT"]] = None,
        issued_at: Optional[datetime] = None,
        state: str = "active",
        rng: Optional[random.Random] = None,
    ) -> "BingoCard":
        """Generate and persist a bingo card for a user.

        Creates a 3x3 BingoCard (centre at index 4) populated with NFT templates.
        The card is added to and flushed on the provided SQLAlchemy session
        before being returned.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        user : User
            Recipient of the card.
        center_template : NFT
            NFT definition assigned to the centre cell (index 4).
        excluded_templates : iterable[int | NFT], optional
            Definitions that must not appear on the card. Can be specified as a list of
            `NFT` objects or their integer primary keys.
        included_templates : iterable[int | NFT], optional
            If provided, the method will select non-centre definitions only from
            this set (after removing any excluded_templates). If omitted or
            empty, definitions are chosen from all available NFT records.
            Can be specified as a list of `NFT` objects or their integer primary keys.
        issued_at : datetime, optional
            Timestamp for card issuance. Defaults to the current UTC time.
        state : str, optional
            Initial card state. Defaults to "active".
        rng : random.Random, optional
            Random generator to use; useful for deterministic tests. If not
            provided, a new non-deterministic generator is used.

        Raises
        ------
        ValueError
            If there are fewer than 8 eligible definitions to fill the non-centre
            cells after applying included/excluded constraints.

        Returns
        -------
        BingoCard
            The newly created BingoCard (already added to the session). Cells
            for which the user already owns a matching NFT will be created in
            the "unlocked" state and linked to that ownership.
        """

        from .ownership import UserNFTOwnership
        from .nft import NFT

        def _to_id(t: int | NFT) -> int:
            return t if isinstance(t, int) else t.id

        rng = rng or random.Random()

        # Convert include/exclude inputs into sets of template IDs
        excluded_ids = {_to_id(t) for t in (excluded_templates or [])}
        included_ids = {_to_id(t) for t in (included_templates or [])}

        if included_ids:
            candidate_ids = set(included_ids)
        else:
            candidate_ids = set(session.scalars(select(NFT.id)))

        candidate_ids.discard(center_template.id)
        candidate_ids -= excluded_ids

        if len(candidate_ids) < 8:
            raise ValueError("Not enough NFTs to populate bingo card")

        # Randomly pick 8 distinct templates for the non-centre cells, then
        # shuffle the destination positions (excluding the centre at 4).
        selected_ids = rng.sample(list(candidate_ids), 8)
        positions = [0, 1, 2, 3, 5, 6, 7, 8]
        rng.shuffle(positions)

        # Create the card itself
        issued_at = issued_at or datetime.now(timezone.utc)
        card = cls(user_id=user.id, issued_at=issued_at, state=state)
        session.add(card)
        session.flush()

        # Fetch any existing UserNFTOwnerships for the selected templates.
        # Matching cells will be created as unlocked, typically including the centre.
        template_ids_needed = set(selected_ids) | {center_template.id}
        ownerships = session.scalars(
            select(UserNFTOwnership)
            .join(NFT)
            .where(
                UserNFTOwnership.user_id == user.id,
                NFT.id.in_(template_ids_needed),
            )
        ).all()
        ownership_map = {o.nft_id: o for o in ownerships}

        # Helper to build a cell
        def build_cell(idx: int, template_id: int) -> "BingoCell":
            ownership = ownership_map.get(template_id)
            # If the user already owns this NFT, build the cell as unlocked
            if ownership is not None:
                return BingoCell(
                    bingo_card_id=card.id,
                    idx=idx,
                    target_template_id=template_id,
                    nft_id=ownership.nft_id,
                    matched_ownership_id=ownership.id,
                    state="unlocked",
                    unlocked_at=datetime.now(timezone.utc),
                )
            # Otherwise, build it as locked
            return BingoCell(
                bingo_card_id=card.id,
                idx=idx,
                target_template_id=template_id,
            )

        # Build the centre cell first, then the others
        cells = [build_cell(4, center_template.id)]
        for idx, tid in zip(positions, selected_ids):
            cells.append(build_cell(idx, tid))

        # Add cells to the card and flush
        card.cells.extend(cells)
        session.flush()

        return card

    # Convenience helpers
    @property
    def winning_lines(self) -> list[tuple[int, int, int]]:
        """Get all possible winning line combinations for a 3x3 bingo card."""
        return [
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        ]

    @property
    def completed_lines(self) -> list[tuple[int, int, int]]:
        """All completed lines in the bingo card.

        The result is a list of tuples containing the indices of cells that form
        completed lines. Each tuple represents the positions of cells in a winning
        line that are all in ``"unlocked"`` state.
        """
        result: list[tuple[int, int, int]] = []
        for a, b, c in self.winning_lines:
            if all(
                cell.state == "unlocked"
                for cell in (self.cells[a], self.cells[b], self.cells[c])
            ):
                result.append((a, b, c))
        return result

    def unlock_cells_for_ownership(
        self, session: Session, ownership: "UserNFTOwnership"
    ) -> bool:
        """Unlock cells matched by the given ownership.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session (unused but kept for API symmetry).
        ownership : UserNFTOwnership
            Ownership to match against locked cells.

        Returns
        -------
        bool
            ``True`` if at least one cell was unlocked, otherwise ``False``.
        """

        unlocked_any = False
        template_id = ownership.nft_id
        for cell in self.cells:
            if cell.state == "locked" and cell.target_template_id == template_id:
                cell.nft_id = ownership.nft_id
                cell.matched_ownership_id = ownership.id
                cell.state = "unlocked"
                cell.unlocked_at = datetime.now(timezone.utc)
                unlocked_any = True

        if unlocked_any and self.completed_at is None:
            if all(cell.state == "unlocked" for cell in self.cells):
                self.completed_at = datetime.now(timezone.utc)
                self.state = "completed"

        return unlocked_any


class BingoCardIssueTask(Base):
    """Outbox-style task for issuing bingo cards asynchronously."""

    __tablename__ = "bingo_card_issue_tasks"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    center_nft_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ownership_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("user_nft_ownership.id", ondelete="CASCADE"),
        nullable=False,
    )
    unique_nft_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','succeeded','failed','blocked')",
            name="bingo_issue_status_enum",
        ),
        UniqueConstraint(
            "ownership_id", name="bingo_card_issue_tasks_ownership_id_key"
        ),
        Index("ix_bingo_issue_status_run", "status", "next_run_at"),
    )


class BingoCell(Base):
    """Single cell within a :class:`BingoCard` grid."""

    def __init__(
        self,
        bingo_card_id: int,
        idx: int,
        target_template_id: int,
        nft_id: Optional[int] = None,
        matched_ownership_id: Optional[int] = None,
        state: str = "locked",
        unlocked_at: Optional[datetime] = None,
    ):
        self.bingo_card_id = bingo_card_id
        self.idx = idx
        self.target_template_id = target_template_id
        self.nft_id = nft_id
        self.matched_ownership_id = matched_ownership_id
        self.state = state
        self.unlocked_at = unlocked_at

    __tablename__ = "bingo_cells"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    bingo_card_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("bingo_cards.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    target_template_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nft_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("nfts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_ownership_id: Mapped[Optional[int]] = mapped_column(
        ID_TYPE, ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    card: Mapped["BingoCard"] = relationship(back_populates="cells")
    target_template: Mapped["NFT"] = relationship(
        "NFT", foreign_keys=[target_template_id]
    )
    nft: Mapped[Optional["NFT"]] = relationship("NFT", foreign_keys=[nft_id])
    matched_ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        "UserNFTOwnership"
    )

    __table_args__ = (
        UniqueConstraint("bingo_card_id", "idx", name="uq_bingo_card_idx"),
        CheckConstraint("state IN ('locked','unlocked')", name="bingo_cell_state_enum"),
        CheckConstraint("idx >= 0 AND idx <= 8", name="bingo_cell_idx_range"),
        Index("ix_bingo_cells_card", "bingo_card_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCell(id={self.id}, idx={self.idx}, target_template_id={self.target_template_id}, "
            f"nft_id={self.nft_id}, state='{self.state}')>"
        )

    def to_json(self, *, compact: bool = False) -> dict[str, Any]:
        """Return a JSON (dict) for this BingoCell.

        When compact is True, keep only essential fields and a compact template.
        """
        template_obj = self.target_template.to_json(compact=compact)

        full = {
            "id": self.id,
            "bingo_card_id": self.bingo_card_id,
            "idx": self.idx,
            "state": self.state,
            "unlocked_at": dt_iso(self.unlocked_at),
            "nft_id": self.nft_id,
            "matched_ownership_id": self.matched_ownership_id,
            "target_template": template_obj,
        }
        if not compact:
            return full
        keep = {"id", "idx", "state", "unlocked_at", "target_template"}
        return {k: v for k, v in full.items() if k in keep}

    def to_json_str(self, *, compact: bool = False) -> str:
        """Serialize this BingoCell to a JSON string.

        Timestamps are formatted as ISO 8601 (UTC) using the dt_iso helper.
        """
        import json

        return json.dumps(self.to_json(compact=compact), ensure_ascii=False)


class PreGeneratedBingoCard(Base):
    """Pool of pre-generated bingo cards."""

    __tablename__ = "pre_generated_bingo_cards"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(Integer, ForeignKey("bingo_periods.id"), nullable=False)
    center_nft_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("nfts.id"), nullable=False)
    cell_nft_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
