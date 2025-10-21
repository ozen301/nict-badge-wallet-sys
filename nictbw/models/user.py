from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Optional, Any
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select

from .nft import NFT, NFTTemplate
from .ownership import UserNFTOwnership
from .base import Base
from .utils import generate_unique_nft_id

if TYPE_CHECKING:
    from ..blockchain.api import ChainClient
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    """A user participating in the NICT project."""

    def __init__(
        self,
        in_app_id: str,
        paymail: Optional[str] = None,
        login_mail: Optional[str] = None,
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

        self.in_app_id = in_app_id
        self.on_chain_id = on_chain_id
        self.nickname = nickname
        self.password_hash = password_hash
        if paymail is not None:
            self.paymail = paymail
        if login_mail is not None:
            self.login_mail = login_mail
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
    login_mail: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
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
            f"nickname='{self.nickname}', on_chain_id='{self.on_chain_id}', "
            f"login_mail='{self.login_mail}', updated_at='{self.updated_at}')>"
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
    def get_by_login_mail(cls, session: Session, login_mail: str) -> Optional["User"]:
        """Retrieve a user by login_mail address."""

        return session.scalar(select(cls).where(cls.login_mail == login_mail))

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

        # Retrieve the latest state of the user's NFTs from the blockchain.
        chain_items = client.get_user_nfts(self.on_chain_id) or []

        from .admin import Admin

        # Helper: normalise timestamps returned by the blockchain API.
        def _parse_datetime(value: Any) -> datetime:
            """Return a timezone-aware datetime for chain-supplied values."""
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
            """Collect metadata embedded in a blockchain NFT payload."""

            meta: dict[str, Any] = {}

            metadata_block = item.get("metadata")
            if isinstance(metadata_block, dict):
                map_block = metadata_block.get("MAP")
                if isinstance(map_block, dict):
                    subtype_data = map_block.get("subTypeData")
                    if isinstance(subtype_data, dict):
                        # The API guarantees metadata is embedded under ``subTypeData``.
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

        # Track already-known NFTs by their on-chain origin so we can decide
        # whether to update an ownership record or create a brand new one.
        existing_nft_origins = {
            ownership.nft.origin: ownership
            for ownership in self.ownerships
            if ownership.nft and ownership.nft.origin
        }

        # Cache expensive per-template counts and remember which templates were
        # touched so that their minted totals can be reconciled afterwards.
        template_nft_counts: dict[int, int] = {}
        touched_template_ids: set[int] = set()
        default_admin_id: Optional[int] = None

        def _template_count(template: NFTTemplate) -> int:
            """Return cached NFT counts per template to align minted totals."""
            if template.id is None:
                session.flush()
            assert template.id is not None
            if template.id not in template_nft_counts:
                template_nft_counts[template.id] = (
                    session.scalar(
                        select(func.count()).where(NFT.template_id == template.id)
                    )
                    or 0
                )
            return template_nft_counts[template.id]

        def _default_admin_id() -> int:
            """Fetch the lowest admin ID for use when creating templates."""
            nonlocal default_admin_id
            if default_admin_id is None:
                default_admin_id = session.scalar(select(func.min(Admin.id)))
                if default_admin_id is None:
                    default_admin_id = 0
            return default_admin_id

        # Process each NFT payload returned by the blockchain.
        for item in chain_items:
            if not isinstance(item, dict):
                continue
            origin = item.get("nft_origin")
            if not origin:
                continue

            metadata = _extract_metadata(item)

            # Determine identifiers and descriptive fields from the metadata.
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

            category_raw = metadata.get("category") or item.get("category")
            category = (
                str(category_raw) if category_raw is not None else "uncategorized"
            )
            category = category[:50]

            subcategory_raw = (
                metadata.get("subcategory")
                or metadata.get("subCategory")
                or item.get("subcategory")
            )
            if subcategory_raw is None:
                subcategory_raw = f"{prefix}-default"
            subcategory = str(subcategory_raw)[:100]

            template_name_raw = metadata.get("name") or item.get("name")
            template_name = (
                str(template_name_raw)[:100]
                if template_name_raw is not None
                else prefix
            )

            description_raw = metadata.get("description") or item.get("description")
            description = str(description_raw) if description_raw is not None else None

            image_url_raw = (
                metadata.get("image_url")
                or metadata.get("imageUrl")
                or item.get("image_url")
            )
            image_url = str(image_url_raw) if image_url_raw is not None else None

            created_at = _parse_datetime(item.get("created_at"))
            updated_at = _parse_datetime(item.get("updated_at"))

            # Ensure a local template exists for the prefix returned on-chain.
            template = NFTTemplate.get_by_prefix(session, prefix)
            if template is None:
                # No template exists locally yet; create a shell from the
                # metadata embedded in the blockchain payload.
                template = NFTTemplate(
                    prefix=prefix,
                    name=template_name,
                    category=category,
                    subcategory=subcategory,
                    description=description,
                    image_url=image_url,
                    created_by_admin_id=_default_admin_id(),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                session.add(template)
                session.flush()

            touched_template_ids.add(template.id)

            # Track the current number of NFTs for mint count reconciliation later.
            current_count = _template_count(template)

            nft = NFT.get_by_origin(session, origin)

            nft_name_raw = metadata.get("name") or item.get("name")
            if nft_name_raw is not None:
                nft_name = str(nft_name_raw)[:100]
            else:
                nft_name = template.name or prefix

            meta_description = (
                description if description is not None else template.description
            )
            meta_image = image_url if image_url is not None else template.image_url
            current_location = item.get("current_nft_location") or origin

            # Create or update the NFT row itself.
            if nft is None:
                nft = NFT(
                    template_id=template.id,
                    prefix=prefix,
                    shared_key=shared_key,
                    name=nft_name,
                    category=category,
                    subcategory=subcategory,
                    description=meta_description,
                    image_url=meta_image,
                    created_by_admin_id=template.created_by_admin_id,
                    id_on_chain=item.get("nft_id"),
                    origin=origin,
                    current_location=current_location,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                session.add(nft)
                session.flush()
                current_count += 1
                template_nft_counts[template.id] = current_count
            else:
                if nft.prefix != prefix:
                    nft.prefix = prefix
                if shared_key and nft.shared_key != shared_key:
                    nft.shared_key = shared_key
                if nft.template_id != template.id:
                    nft.template_id = template.id
                if nft.name != nft_name:
                    nft.name = nft_name
                if category and nft.category != category:
                    nft.category = category
                if subcategory and nft.subcategory != subcategory:
                    nft.subcategory = subcategory
                if meta_description is not None and nft.description != meta_description:
                    nft.description = meta_description
                if meta_image is not None and nft.image_url != meta_image:
                    nft.image_url = meta_image
                # Always align created/updated timestamps to on-chain source
                nft.created_at = created_at
                nft.id_on_chain = item.get("nft_id", nft.id_on_chain)
                nft.current_location = current_location
                nft.updated_at = updated_at
                template_nft_counts[template.id] = current_count

            meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

            ownership = existing_nft_origins.get(origin)
            if ownership is not None:
                # Refresh stored metadata to match what is currently on chain.
                if ownership.other_meta != meta_json:
                    ownership.other_meta = meta_json
                provided_unique_id = item.get("unique_nft_id")
                if provided_unique_id:
                    truncated = str(provided_unique_id)[:255]
                    if ownership.unique_nft_id != truncated:
                        ownership.unique_nft_id = truncated
                if created_at:
                    ownership.acquired_at = created_at
                continue

            provided_unique_id = item.get("unique_nft_id")
            if provided_unique_id:
                unique_nft_id = str(provided_unique_id)[:255]
            else:
                unique_nft_id = generate_unique_nft_id(prefix, session=session)
            serial = max(template_nft_counts.get(template.id, current_count) - 1, 0)
            # The NFT is new to the local database; create a corresponding
            # ownership entry for this user.
            ownership = UserNFTOwnership(
                user_id=self.id,
                nft_id=nft.id,
                serial_number=serial,
                unique_nft_id=unique_nft_id,
                acquired_at=created_at,
                other_meta=meta_json,
            )
            session.add(ownership)
            existing_nft_origins[origin] = ownership

        # Align minted counts for each template touched during the sync.
        for template_id in touched_template_ids:
            template_obj = session.get(NFTTemplate, template_id)
            if template_obj is None:
                continue
            count = template_nft_counts.get(template_id)
            if count is None:
                count = (
                    session.scalar(
                        select(func.count()).where(NFT.template_id == template_id)
                    )
                    or 0
                )
                template_nft_counts[template_id] = count
            if template_obj.minted_count < count:
                template_obj.minted_count = count

        session.flush()

        # The commit is handled by the caller, not here.
