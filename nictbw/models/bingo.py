from datetime import datetime, timezone
import random
from typing import TYPE_CHECKING, Iterable, Optional
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    select,
)
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT, NFTTemplate
    from .ownership import UserNFTOwnership


class BingoCard(Base):
    """Bingo card assigned to a user.

    Represents a 3x3 grid of :class:`BingoCell` objects that can be unlocked by
    collecting NFTs matching predefined templates.
    """

    def __init__(
        self,
        user_id: int,
        issued_at: datetime,
        completed_at: Optional[datetime] = None,
        state: str = "active",
    ):
        self.user_id = user_id
        self.issued_at = issued_at
        self.completed_at = completed_at
        self.state = state

    __tablename__ = "bingo_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    user: Mapped["User"] = relationship(back_populates="bingo_cards")
    cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("state IN ('active','completed','expired')", name="state_enum"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCard(id={self.id}, user_id={self.user_id}, "
            f"issued_at={self.issued_at}, state='{self.state}')>"
        )

    @classmethod
    def generate_for_user(
        cls,
        session: Session,
        user: "User",
        center_template: "NFTTemplate",
        *,
        excluded_templates: Optional[Iterable["int | NFTTemplate"]] = None,
        included_templates: Optional[Iterable["int | NFTTemplate"]] = None,
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
        center_template : NFTTemplate
            Template assigned to the centre cell (index 4).
        excluded_templates : iterable[int | NFTTemplate], optional
            Templates that must not appear on the card. Can be specified as a list of
            `NFTTemplate` objects or their integer primary keys.
        included_templates : iterable[int | NFTTemplate], optional
            If provided, the method will select non-centre templates only from
            this set (after removing any excluded_templates). If omitted or
            empty, templates are chosen from all available NFTTemplate records.
            Can be specified as a list of `NFTTemplate` objects or their integer primary keys.
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
            If there are fewer than 8 eligible templates to fill the non-centre
            cells after applying included/excluded constraints.

        Returns
        -------
        BingoCard
            The newly created BingoCard (already added to the session). Cells
            for which the user already owns a matching NFT will be created in
            the "unlocked" state and linked to that ownership.
        """

        from .ownership import UserNFTOwnership
        from .nft import NFT, NFTTemplate

        def _to_id(t: int | NFTTemplate) -> int:
            return t if isinstance(t, int) else t.id

        rng = rng or random.Random()

        # Convert include/exclude inputs into sets of template IDs
        excluded_ids = {_to_id(t) for t in (excluded_templates or [])}
        included_ids = {_to_id(t) for t in (included_templates or [])}

        if included_ids:
            candidate_ids = set(included_ids)
        else:
            candidate_ids = set(session.scalars(select(NFTTemplate.id)))

        candidate_ids.discard(center_template.id)
        candidate_ids -= excluded_ids

        if len(candidate_ids) < 8:
            raise ValueError("Not enough NFT templates to populate bingo card")

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
                NFT.template_id.in_(template_ids_needed),
            )
        ).all()
        ownership_map = {o.nft.template_id: o for o in ownerships}

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
        template_id = ownership.nft.template_id
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bingo_card_id: Mapped[int] = mapped_column(
        ForeignKey("bingo_cards.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    target_template_id: Mapped[int] = mapped_column(
        ForeignKey("nft_templates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_ownership_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_nft_ownership.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    card: Mapped["BingoCard"] = relationship(back_populates="cells")
    target_template: Mapped["NFTTemplate"] = relationship(back_populates="target_cells")
    nft: Mapped[Optional["NFT"]] = relationship(back_populates="target_cell")
    matched_ownership: Mapped[Optional["UserNFTOwnership"]] = relationship(
        back_populates="matched_cells"
    )

    __table_args__ = (
        UniqueConstraint("bingo_card_id", "idx", name="uq_card_idx"),
        CheckConstraint("state IN ('locked','unlocked')", name="state_enum"),
        CheckConstraint(
            "(state = 'locked' AND nft_id IS NULL AND matched_ownership_id IS NULL) OR "
            "(state = 'unlocked' AND nft_id IS NOT NULL AND matched_ownership_id IS NOT NULL)",
            name="locked_unlocked_consistency",
        ),
        CheckConstraint("idx >= 0 AND idx <= 8", name="idx_range"),
        Index("ix_bingo_cells_card", "bingo_card_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BingoCell(id={self.id}, idx={self.idx}, target_template_id={self.target_template_id}, "
            f"nft_id={self.nft_id}, state='{self.state}')>"
        )
