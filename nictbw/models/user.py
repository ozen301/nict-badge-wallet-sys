from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import Boolean, DateTime, String, func, select, text, UniqueConstraint
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship, synonym, validates

from .id_type import ID_TYPE
from .base import Base
from .ownership import NFTInstance

if TYPE_CHECKING:
    from ..blockchain.api import ChainClient
    from .bingo import BingoCard
    from .coupon import CouponInstance
    from .nft import NFTDefinition
    from .prize_draw import PrizeDrawResult, RaffleEntry, RaffleEvent


class User(Base):
    """A user participating in the NICT project."""

    def __init__(
        self,
        in_app_id: Optional[str] = None,
        *,
        uid: Optional[str] = None,
        email: Optional[str] = None,
        paymail: Optional[str] = None,
        on_chain_id: Optional[str] = None,
        nickname: Optional[str] = None,
        password_hash: Optional[str] = None,
        password_provided: Optional[bool] = None,
        fcm_token: Optional[str] = None,
        initial_reward_claimed: Optional[bool] = None,
        is_test_user: Optional[bool] = None,
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
        login_mail : str, optional
            User's login email address.
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

        if in_app_id is None:
            in_app_id = uid
        self.in_app_id = in_app_id
        self.email = email
        self.on_chain_id = on_chain_id
        self.nickname = nickname
        self.password_hash = password_hash
        self.paymail = paymail
        if password_provided is not None:
            self.password_provided = password_provided
        if fcm_token is not None:
            self.fcm_token = fcm_token
        if initial_reward_claimed is not None:
            self.initial_reward_claimed = initial_reward_claimed
        if is_test_user is not None:
            self.is_test_user = is_test_user
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, index=True, autoincrement=True
    )
    in_app_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_provided: Mapped[bool] = mapped_column(Boolean, default=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    paymail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    on_chain_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fcm_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    initial_reward_claimed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    is_test_user: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("paymail", name="users_paymail_key"),
    )

    uid = synonym("in_app_id")
    login_mail = synonym("email")

    # relationships
    ownerships: Mapped[list["NFTInstance"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bingo_cards: Mapped[list["BingoCard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    raffle_entries: Mapped[list["RaffleEntry"]] = relationship(
        "RaffleEntry",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    prize_draw_results: Mapped[list["PrizeDrawResult"]] = relationship(
        "PrizeDrawResult",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    raffle_events_won: Mapped[list["RaffleEvent"]] = relationship(
        "RaffleEvent",
        back_populates="winner_user",
        foreign_keys="RaffleEvent.winner_user_id",
    )
    coupons: Mapped[list["CouponInstance"]] = relationship(
        "CouponInstance",
        back_populates="user",
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, in_app_id='{self.in_app_id}', "
            f"nickname='{self.nickname}', on_chain_id='{self.on_chain_id}', "
            f"email='{self.email}', updated_at='{self.updated_at}')>"
        )

    @validates("email")
    def _normalize_email(self, _key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @classmethod
    def get_by_in_app_id(cls, session: Session, in_app_id: str) -> Optional["User"]:
        """Retrieve a user by their in_app_id."""

        return session.scalar(select(cls).where(cls.in_app_id == in_app_id))

    @classmethod
    def get_by_paymail(cls, session: Session, paymail: str) -> Optional["User"]:
        """Retrieve a user by paymail address."""

        return session.scalar(select(cls).where(cls.paymail == paymail))

    @classmethod
    def get_by_login_mail(cls, session: Session, login_mail: str) -> Optional["User"]:
        """Backward-compatible alias for email lookup."""
        return session.scalar(select(cls).where(cls.email == login_mail))

    @classmethod
    def get_by_email(cls, session: Session, email: str) -> Optional["User"]:
        """Retrieve a user by email address."""
        return session.scalar(select(cls).where(cls.email == email))

    @classmethod
    def get_by_on_chain_id(cls, session: Session, on_chain_id: str) -> Optional["User"]:
        """Retrieve a user by on_chain_id."""

        return session.scalar(select(cls).where(cls.on_chain_id == on_chain_id))

    @property
    def nfts(self) -> list[NFTInstance]:
        """Get NFT instances owned by this user."""
        return list(self.ownerships)

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

    def unlock_bingo_cells(self, session: Session, ownership: NFTInstance) -> bool:
        """Unlock bingo cells on this user's active cards.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        ownership : NFTInstance
            Newly created ownership to match against bingo cells.

        Returns
        -------
        bool
            ``True`` if any cell was unlocked.
        """

        from .bingo import BingoCard

        unlocked_any = False
        cards = session.scalars(
            select(BingoCard).where(
                BingoCard.user_id == self.id,
                BingoCard.state == "active",
            )
        ).all()
        for card in cards:
            if card.unlock_cells_for_ownership(session, ownership):
                unlocked_any = True

        return unlocked_any

    def unlock_cells_for_definition(
        self, session: Session, definition: "NFTDefinition | int"
    ) -> bool:
        """Unlock bingo cells for a specific NFT definition owned by this user.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        definition : NFTDefinition | int
            The NFT definition to match against locked cells. Can be an
            ``NFTDefinition`` instance or its primary key.

        Returns
        -------
        bool
            ``True`` if any cell was unlocked, otherwise ``False``.
        """

        def _to_id(n: int | NFTDefinition) -> int:
            return n if isinstance(n, int) else n.id

        ownership = NFTInstance.get_by_user_and_definition(
            session, self.id, _to_id(definition)
        )
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
        from .nft import NFTDefinition

        triggering_nfts = session.scalars(
            select(NFTDefinition)
            .join(NFTInstance)
            .where(
                NFTInstance.user_id == self.id,
                NFTDefinition.triggers_bingo_card.is_(True),
            )
            .distinct()
        ).all()

        # For each template, check if a corresponding bingo card already exists
        created = 0
        for nft in triggering_nfts:
            exists = session.scalar(
                select(BingoCard)
                .join(BingoCell)
                .where(
                    BingoCard.user_id == self.id,
                    BingoCell.idx == 4,
                    BingoCell.target_definition_id == nft.id,
                )
            )
            # If not, create one
            if exists is None:
                BingoCard.generate_for_user(session, self, nft)
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
        from .ownership import NFTInstance
        from .nft import NFTDefinition

        # Reload relationships to capture newly created cards or ownerships
        session.expire(self, ["bingo_cards", "ownerships"])

        # Map definition_id -> ownership for quick lookup
        ownerships = session.scalars(
            select(NFTInstance)
            .join(NFTDefinition)
            .where(NFTInstance.user_id == self.id)
        ).all()
        ownership_map = {o.definition_id: o for o in ownerships}

        unlocked = 0
        for card in self.bingo_cards:
            if card.state != "active":
                continue
            card_unlocked = False
            for cell in card.cells:
                if cell.state == "locked":
                    ownership = ownership_map.get(cell.target_definition_id)
                    if ownership is not None:
                        cell.nft_id = ownership.definition_id
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
          ``NFTDefinition`` and ``NFTInstance`` records exist locally.
        - Newly seen on-chain NFTs are created in the DB using the metadata
          embedded in the chain records, with fallbacks only when information is
          unavailable.
        - Caller is responsible for managing the outer transaction (commit/rollback).
        """

        if self.on_chain_id is None:
            raise ValueError("User does not have an on-chain ID set.")

        if client is None:
            from ..blockchain.api import ChainClient

            client = ChainClient()

        chain_items = client.get_user_nfts(self.on_chain_id) or []

        from .admin import Admin
        from .nft import NFTDefinition
        from .ownership import NFTInstance
        from .utils import generate_unique_nft_id

        def _parse_datetime(value: Any) -> datetime:
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if isinstance(value, str):
                normalized = value.strip()
                if normalized.endswith("Z"):
                    normalized = normalized[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(normalized)
                except ValueError:
                    return datetime.now(timezone.utc)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            return datetime.now(timezone.utc)

        def _extract_metadata(item: dict[str, Any]) -> dict[str, Any]:
            meta: dict[str, Any] = {}
            metadata_block = item.get("metadata")
            if isinstance(metadata_block, dict):
                map_block = metadata_block.get("MAP")
                if isinstance(map_block, dict):
                    subtype_data = map_block.get("subTypeData")
                    if isinstance(subtype_data, dict):
                        for key, value in subtype_data.items():
                            if value is not None and key not in meta:
                                meta[key] = value
                    map_name = map_block.get("name")
                    if map_name and "name" not in meta:
                        meta["name"] = map_name

            key_aliases = {
                "sharedKey": "shared_key",
                "subCategory": "subcategory",
                "imageUrl": "image_url",
                "conditionId": "condition_id",
            }
            for alias, canonical in key_aliases.items():
                if alias in meta and canonical not in meta:
                    meta[canonical] = meta[alias]

            for key in (
                "prefix",
                "shared_key",
                "category",
                "subcategory",
                "description",
                "image_url",
                "name",
            ):
                value = item.get(key)
                if key not in meta and value is not None:
                    meta[key] = value

            return meta

        default_admin_id: Optional[int] = None

        def _default_admin_id() -> int:
            nonlocal default_admin_id
            if default_admin_id is None:
                default_admin_id = session.scalar(select(func.min(Admin.id)))
                if default_admin_id is None:
                    default_admin_id = 0
            return default_admin_id

        touched_nft_ids: set[int] = set()
        nft_updated_at_map: dict[int, datetime] = {}

        for item in chain_items:
            if not isinstance(item, dict):
                continue

            origin = (
                item.get("nft_origin")
                or item.get("origin")
                or item.get("txid")
                or item.get("transaction_id")
            )
            if not origin:
                continue

            metadata = _extract_metadata(item)

            prefix_raw = metadata.get("prefix") or item.get("prefix")
            prefix = str(prefix_raw) if prefix_raw is not None else f"onchain-{origin}"
            prefix = prefix[:100]

            shared_key_raw = (
                metadata.get("shared_key")
                or metadata.get("sharedKey")
                or item.get("shared_key")
                or item.get("sharedKey")
            )
            shared_key = str(shared_key_raw) if shared_key_raw is not None else origin
            shared_key = shared_key[:255]

            name_raw = metadata.get("name") or item.get("name")
            name = str(name_raw)[:100] if name_raw is not None else prefix

            nft_type = str(item.get("nft_type") or metadata.get("nft_type") or "default")[:50]
            category = metadata.get("category") or item.get("category")
            category = str(category)[:50] if category is not None else None
            subcategory = metadata.get("subcategory") or item.get("subcategory")
            subcategory = str(subcategory)[:50] if subcategory is not None else None
            description = metadata.get("description") or item.get("description")
            image_url = (
                metadata.get("image_url")
                or metadata.get("imageUrl")
                or item.get("image_url")
            )

            created_at = _parse_datetime(item.get("created_at"))
            updated_at = _parse_datetime(item.get("updated_at"))

            nft = session.scalar(select(NFTDefinition).where(NFTDefinition.prefix == prefix))
            if nft is None:
                nft = NFTDefinition(
                    prefix=prefix,
                    shared_key=shared_key,
                    name=name,
                    nft_type=nft_type,
                    category=category,
                    subcategory=subcategory,
                    description=description,
                    image_url=image_url,
                    condition_id=metadata.get("condition_id"),
                    created_by_admin_id=_default_admin_id(),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                session.add(nft)
                session.flush()
            else:
                nft.name = name
                nft.nft_type = nft_type
                nft.category = category
                nft.subcategory = subcategory
                nft.description = description
                nft.image_url = image_url
                nft.shared_key = shared_key
                nft.created_at = created_at
                nft.updated_at = updated_at

            touched_nft_ids.add(nft.id)
            nft_updated_at_map[nft.id] = updated_at

            meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
            current_location = item.get("current_nft_location") or origin

            ownership = NFTInstance.get_by_user_and_definition(session, self.id, nft.id)
            provided_unique_id = item.get("unique_nft_id")
            if ownership is None:
                if provided_unique_id:
                    unique_nft_id = str(provided_unique_id)[:255]
                else:
                    unique_nft_id = generate_unique_nft_id(prefix, session=session)

                ownership = NFTInstance(
                    user_id=self.id,
                    definition_id=nft.id,
                    serial_number=nft.minted_count,
                    unique_nft_id=unique_nft_id,
                    acquired_at=created_at,
                    status="succeeded",
                )
                session.add(ownership)
                nft.minted_count += 1
            elif provided_unique_id:
                ownership.unique_nft_id = str(provided_unique_id)[:255]

            ownership.acquired_at = created_at
            ownership.blockchain_nft_id = item.get("nft_id")
            ownership.nft_origin = origin
            ownership.current_nft_location = current_location
            ownership.blockchain_name = item.get("name")
            ownership.sub_type = item.get("sub_type") or metadata.get("sub_type")
            ownership.blockchain_created_at = _parse_datetime(item.get("created_at"))
            ownership.blockchain_updated_at = _parse_datetime(item.get("updated_at"))
            ownership.transaction_id = item.get("transaction_id") or origin
            ownership.contract_address = item.get("contract_address")
            ownership.token_id = item.get("token_id")
            ownership.other_meta = meta_json

        for nft_id in touched_nft_ids:
            nft_obj = session.get(NFTDefinition, nft_id)
            if nft_obj is None:
                continue
            count = session.scalar(
                select(func.count()).where(NFTInstance.definition_id == nft_id)
            )
            nft_obj.minted_count = int(count or 0)
            updated_at = nft_updated_at_map.get(nft_id)
            if updated_at is not None:
                nft_obj.updated_at = updated_at

        session.flush()

        if nft_updated_at_map:
            from sqlalchemy import update
            from sqlalchemy.orm.attributes import set_committed_value

            for nft_id, updated_at in nft_updated_at_map.items():
                session.execute(
                    update(NFTDefinition)
                    .where(NFTDefinition.id == nft_id)
                    .values(updated_at=updated_at)
                )
                nft_obj = session.get(NFTDefinition, nft_id)
                if nft_obj is not None:
                    set_committed_value(nft_obj, "updated_at", updated_at)

        session.flush()
