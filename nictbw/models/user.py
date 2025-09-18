from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Any
import warnings
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select

from .nft import NFT, NFTTemplate
from .ownership import UserNFTOwnership
from .base import Base

if TYPE_CHECKING:
    from nictbw.blockchain.api import ChainClient
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    """A user participating in the NICT project."""

    def __init__(
        self,
        in_app_id: str,
        paymail: Optional[str] = None,
        on_chain_id: Optional[str] = None,
        nickname: Optional[str] = None,
        password_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Create a new :class:`User` record.

        Parameters
        ----------
        in_app_id : str
            User's ID in the mobile app.
        paymail : str, optional
            User's paymail address. It can be left ``None`` until the blockchain
            registration workflow supplies the generated paymail.
        on_chain_id : str, optional
            Corresponding blockchain ID.
        nickname : str, optional
            Display name.
        password_hash : str, optional
            Hashed password.
        created_at : datetime, optional
            Explicit creation timestamp.
        updated_at : datetime, optional
            Explicit last update timestamp.
        """

        self.in_app_id = in_app_id
        self.on_chain_id = on_chain_id
        self.nickname = nickname
        self.password_hash = password_hash
        if paymail is not None:
            self.paymail = paymail
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    in_app_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    paymail: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=False
    )
    on_chain_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    ownerships: Mapped[list["UserNFTOwnership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bingo_cards: Mapped[list["BingoCard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chain_txs: Mapped[list["BlockchainTransaction"]] = relationship(
        "BlockchainTransaction",
        primaryjoin="User.paymail==BlockchainTransaction.user_paymail",
        back_populates="user",
        viewonly=False,
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, in_app_id='{self.in_app_id}', "
            f"nickname='{self.nickname}', on_chain_id='{self.on_chain_id}', updated_at='{self.updated_at}')>"
        )

    @classmethod
    def get_by_in_app_id(cls, session: Session, in_app_id: str) -> Optional["User"]:
        """Retrieve a user by their in_app_id."""

        return session.scalar(select(cls).where(cls.in_app_id == in_app_id))

    @classmethod
    def get_by_paymail(cls, session: Session, paymail: str) -> Optional["User"]:
        """Retrieve a user by paymail address."""

        return session.scalar(select(cls).where(cls.paymail == paymail))

    @classmethod
    def get_by_on_chain_id(cls, session: Session, on_chain_id: str) -> Optional["User"]:
        """Retrieve a user by on_chain_id."""

        return session.scalar(select(cls).where(cls.on_chain_id == on_chain_id))

    @property
    def nfts(self) -> list[NFT]:
        """Get a list of NFTs owned by this user."""
        return [o.nft for o in self.ownerships]

    def bingo_cards_json(self, *, compact: bool = False) -> list[dict[str, Any]]:
        """Return a list of this user's bingo cards as JSON-serializable dicts.

        Uses :meth:`BingoCard.to_json` for each card. By default returns full
        representations unless ``compact`` is True.
        """
        return [card.to_json(compact=compact) for card in self.bingo_cards]

    def bingo_cards_json_str(self, *, compact: bool = False) -> str:
        """Serialize this user's bingo cards to a JSON string."""
        import json

        return json.dumps(self.bingo_cards_json(compact=compact), ensure_ascii=False)

    def unlock_bingo_cells(self, session: Session, ownership: UserNFTOwnership) -> bool:
        """Unlock bingo cells on this user's active cards.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        ownership : UserNFTOwnership
            Newly created ownership to match against bingo cells.

        Returns
        -------
        bool
            ``True`` if any cell was unlocked.
        """

        unlocked_any = False
        for card in self.bingo_cards:
            if card.state == "active":
                if card.unlock_cells_for_ownership(session, ownership):
                    unlocked_any = True

        return unlocked_any

    def unlock_cells_for_nft(self, session: Session, nft: "NFT | int") -> bool:
        """Unlock bingo cells for a specific NFT owned by this user.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        nft : NFT | int
            The NFT to match against locked cells. Can be an ``NFT`` instance or its primary key.

        Returns
        -------
        bool
            ``True`` if any cell was unlocked, otherwise ``False``.
        """

        def _to_id(n: int | NFT) -> int:
            return n if isinstance(n, int) else n.id

        ownership = UserNFTOwnership.get_by_user_and_nft(session, self.id, _to_id(nft))
        if ownership is None:
            return False

        # Reload bingo cards to ensure newly created cards are considered
        session.expire(self, ["bingo_cards"])
        return self.unlock_bingo_cells(session, ownership)

    def ensure_bingo_cards(self, session: Session) -> int:
        """Create bingo cards for owned templates that trigger them.

        Returns
        -------
        int
            Number of newly created bingo cards.
        """

        from sqlalchemy import select
        from .bingo import BingoCard, BingoCell

        # Select the templates the user owns that trigger bingo cards
        triggering_templates = session.scalars(
            select(NFTTemplate)
            .join(NFT)
            .join(UserNFTOwnership)
            .where(
                UserNFTOwnership.user_id == self.id,
                NFTTemplate.triggers_bingo_card.is_(True),
            )
            .distinct()
        ).all()

        # For each template, check if a corresponding bingo card already exists
        created = 0
        for tpl in triggering_templates:
            exists = session.scalar(
                select(BingoCard)
                .join(BingoCell)
                .where(
                    BingoCard.user_id == self.id,
                    BingoCell.idx == 4,
                    BingoCell.target_template_id == tpl.id,
                )
            )
            # If not, create one
            if exists is None:
                card = BingoCard.generate_for_user(session, self, tpl)
                self.bingo_cards.append(card)
                created += 1

        return created

    def ensure_bingo_cells(self, session: Session) -> int:
        """Unlock bingo cells for NFTs already owned by this user.

        Returns
        -------
        int
            Number of cells unlocked.
        """

        from sqlalchemy import select
        from .ownership import UserNFTOwnership
        from .nft import NFT

        # Reload relationships to capture newly created cards or ownerships
        session.expire(self, ["bingo_cards", "ownerships"])

        # Map template_id -> ownership for quick lookup
        ownerships = session.scalars(
            select(UserNFTOwnership)
            .join(NFT)
            .where(UserNFTOwnership.user_id == self.id)
        ).all()
        ownership_map = {o.nft.template_id: o for o in ownerships}

        unlocked = 0
        for card in self.bingo_cards:
            if card.state != "active":
                continue
            card_unlocked = False
            for cell in card.cells:
                if cell.state == "locked":
                    ownership = ownership_map.get(cell.target_template_id)
                    if ownership is not None:
                        cell.nft_id = ownership.nft_id
                        cell.matched_ownership_id = ownership.id
                        cell.state = "unlocked"
                        cell.unlocked_at = datetime.now(timezone.utc)
                        unlocked += 1
                        card_unlocked = True
            if card_unlocked and card.completed_at is None:
                if all(c.state == "unlocked" for c in card.cells):
                    card.completed_at = datetime.now(timezone.utc)
                    card.state = "completed"

        return unlocked

    def set_password_hash(self, new_password_hash: Optional[str]) -> None:
        """Set or clear the stored password hash.

        Parameters
        ----------
        new_password_hash : str or None
            New password hash, or ``None`` to remove it.
        """

        if new_password_hash is None:
            self.password_hash = None
        else:
            self.password_hash = new_password_hash
        self.updated_at = datetime.now(timezone.utc)

    def verify_password_hash(self, password_hash: str) -> bool:
        """Check whether ``password_hash`` matches the stored hash.

        Returns
        -------
        bool
            ``True`` if the hashes match, otherwise ``False``.
        """

        return self.password_hash is not None and self.password_hash == password_hash

    def sync_nfts_from_chain(
        self, session: Session, client: Optional["ChainClient"] = None
    ) -> None:
        """Refresh this user's NFT ownership using the blockchain API.

        Warning
        -------
        WIP/Experimental: This method is not finalized and may change or be removed.
        Do not rely on it in production. Behavior and schema are subject to change.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session used to query and persist changes.
        client : Optional[ChainClient]
            Pre-initialized blockchain client. If ``None``, a new client is created.

        Raises
        ------
        ValueError
            If the user does not have an ``on_chain_id`` set.

        Notes
        -----
        - Fetches NFTs from the chain for ``on_chain_id`` and ensures matching
          ``NFT`` and ``UserNFTOwnership`` records exist locally.
        - Newly seen on-chain NFTs are created in the DB with placeholder fields
          where information is not available on chain.
        - Caller is responsible for managing the outer transaction (commit/rollback).
        """
        # Emit a runtime warning so callers see that this is work-in-progress.
        warnings.warn(
            "User.sync_nfts_from_chain is WIP/experimental and may change or be removed; "
            "avoid using in production.",
            category=UserWarning,
            stacklevel=2,
        )
        if self.on_chain_id is None:
            raise ValueError("User does not have an on-chain ID set.")

        from nictbw.blockchain.api import ChainClient

        client = client or ChainClient()

        chain_items = client.get_user_nfts(self.on_chain_id)

        existing_nft_origins = {o.nft.origin: o for o in self.ownerships}
        on_chain_nft_origins: set[str] = set()

        for item in chain_items:
            origin = item["nft_origin"]
            on_chain_nft_origins.add(origin)

            # Fetch or create the corresponding template and NFT record
            template = NFTTemplate.get_by_prefix(session, origin)
            if template is None:
                template = NFTTemplate(
                    prefix=origin,  # placeholder
                    name=item.get("name", "Unnamed NFT"),
                    category=item.get("type", "default"),
                    subcategory=item.get("sub_type", "default"),
                    description="default description",  # placeholder
                    created_by_admin_id=0,  # placeholder
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
                session.add(template)
                session.flush()

            nft = NFT.get_by_origin(session, origin)
            if nft is None:
                nft = NFT(
                    template_id=template.id,
                    shared_key="unknown",  # placeholder
                    origin=origin,
                    created_by_admin_id=template.created_by_admin_id,
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
                session.add(nft)
                session.flush()

            # Add ownership if not already present
            if origin not in existing_nft_origins:
                serial = template.minted_count
                template.minted_count += 1
                session.add(
                    UserNFTOwnership(
                        user_id=self.id,
                        nft_id=nft.id,
                        serial_number=serial,
                        unique_nft_id=f"{template.prefix}_unknown",  # placeholder
                        acquired_at=datetime.fromisoformat(item["created_at"]),
                    )
                )

        # Remove stale ownerships
        # TODO: confirm if this is necessary
        # for ownership in self.ownerships:
        #     if ownership.nft.origin not in on_chain_nft_origins:
        #         session.delete(ownership)
        # This will remove ownerships that are in the DB but not on chain.
        # It works because ownerships are set to "ON DELETE CASCADE".

        session.flush()

        # The commit is handled by the caller, not here.
