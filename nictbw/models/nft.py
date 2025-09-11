from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    select,
    func,
    inspect,
)
from .base import Base

if TYPE_CHECKING:
    from .ownership import UserNFTOwnership
    from .bingo import BingoCell
    from .chain import BlockchainTransaction
    from nictbw.blockchain.api import ChainClient


class NFTCondition(Base):
    """Constraints that govern when an NFT can be used or issued."""

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location_range: Optional[str] = None,
        required_nft_id: Optional[int] = None,
        prohibited_nft_id: Optional[int] = None,
        other_conditions: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Create a new :class:`NFTCondition`.

        Parameters
        ----------
        start_time : datetime, optional
            Earliest time when the NFT is valid.
        end_time : datetime, optional
            Time after which the NFT becomes invalid.
        location_range : str, optional
            Geographical constraints encoded as a JSON string.
        required_nft_id : int, optional
            ID of an NFT that must be possessed.
        prohibited_nft_id : int, optional
            ID of an NFT that must *not* be possessed.
        other_conditions : str, optional
            JSON string describing additional conditions.
        created_at : datetime, optional
            Explicit creation timestamp.
        updated_at : datetime, optional
            Explicit last update timestamp.
        """

        self.start_time = start_time
        self.end_time = end_time
        self.location_range = location_range
        self.required_nft_id = required_nft_id
        self.prohibited_nft_id = prohibited_nft_id
        self.other_conditions = other_conditions
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "nft_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    location_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    prohibited_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    other_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<NFTCondition(id={self.id}, start_time={self.start_time}, "
            f"end_time={self.end_time}, location_range='{self.location_range}', "
            f"updated_at={self.updated_at})>"
        )


class NFTTemplate(Base):
    """Blueprint from which individual NFTs are instantiated."""

    def __init__(
        self,
        prefix: str,
        name: str,
        category: str,
        subcategory: str,
        created_by_admin_id: int,
        default_condition: Optional[NFTCondition] = None,
        default_condition_id: Optional[int] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        max_supply: Optional[int] = None,
        minted_count: int = 0,
        status: str = "active",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Create a new :class:`NFTTemplate`.

        Parameters
        ----------
        prefix : str
            Unique prefix of the NFT template.
        name : str
            Display name of the template.
        category : str
            Broad category classification, e.g. "game", "restaurant", "event", etc.
        subcategory : str
            More specific classification, such as the name of a restaurant or event.
        created_by_admin_id : int
            Admin responsible for creating the template.
        default_condition : NFTCondition, optional
            Default usage condition associated with NFTs from this template. Either this
            or ``default_condition_id`` can be provided.
        default_condition_id : int, optional
            Primary key of the default condition if the object isn't loaded. Either this
            or ``default_condition`` can be provided.
        description : str, optional
            Human-readable description.
        image_url : str, optional
            URL to the template's image.
        max_supply : int, optional
            Maximum number of NFTs that can be minted from this template.
        minted_count : int, optional
            Number of NFTs already minted. Defaults to ``0``.
        status : str, optional
            Template status (e.g., ``"active"``). Defaults to ``"active"``.
        created_at : datetime, optional
            Explicit creation timestamp.
        updated_at : datetime, optional
            Explicit last update timestamp.
        """

        if default_condition and default_condition_id:
            raise ValueError(
                "Provide either default_condition or default_condition_id, not both."
            )
        if default_condition is not None:
            # Assign relationship; SQLAlchemy will handle the foreign key
            # `default_condition_id` on flush.
            self.default_condition = default_condition
        else:
            self.default_condition_id = default_condition_id

        self.prefix = prefix
        self.name = name
        self.category = category
        self.subcategory = subcategory
        self.created_by_admin_id = created_by_admin_id
        self.description = description
        self.image_url = image_url
        self.max_supply = max_supply
        self.minted_count = minted_count
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    __tablename__ = "nft_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    default_condition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nft_conditions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    default_condition: Mapped[Optional[NFTCondition]] = relationship(
        foreign_keys=[default_condition_id]
    )
    nfts: Mapped[list["NFT"]] = relationship(back_populates="template")
    target_cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="target_template"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive','archived')", name="status_enum"
        ),
        UniqueConstraint("category", "subcategory", name="uq_category_subcategory"),
    )

    def __repr__(self) -> str:
        return (
            f"<NFTTemplate(id={self.id}, prefix='{self.prefix}', category='{self.category}', "
            f"subcategory='{self.subcategory}', minted_count={self.minted_count})>"
        )

    # --- utility methods ---
    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["NFTTemplate"]:
        """Retrieve a template by its unique prefix."""

        stmt = select(cls).where(cls.prefix == prefix)
        return session.scalar(stmt)

    def instantiate_nft(
        self,
        shared_key: str,
        override_name: Optional[str] = None,
        override_description: Optional[str] = None,
        override_created_by_admin_id: Optional[int] = None,
    ) -> "NFT":
        """Instantiate an :class:`NFT` based on this template.

        Parameters
        ----------
        shared_key : str
            Shared key to associate with the new NFT.
        override_name : Optional[str]
            Optionally override the name. Defaults to the template's ``name``.
        override_description : Optional[str]
            Optionally override the description. Defaults to the template's
            ``description``.
        override_created_by_admin_id : Optional[int]
            Optionally override the creator admin ID. Defaults to the template's
            ``created_by_admin_id``.

        Returns
        -------
        NFT
            An ``NFT`` instance mirroring this template's metadata. Note that this
            method does NOT save the instance to the database. The caller is responsible
            for adding and committing it to the session as needed.
        """
        if self.max_supply is not None and self.minted_count >= self.max_supply:
            raise ValueError("Max supply for this template has been reached")

        nft = NFT(
            template_id=self.id,
            prefix=self.prefix,
            shared_key=shared_key,
            name=override_name or self.name,
            category=self.category,
            subcategory=self.subcategory,
            description=override_description or self.description,
            image_url=self.image_url,
            condition_id=self.default_condition_id,
            created_by_admin_id=override_created_by_admin_id
            or self.created_by_admin_id,
        )
        return nft


class NFT(Base):
    """Instance of an NFT."""

    def __init__(
        self,
        shared_key: str,
        template_id: int,
        prefix: Optional[str] = None,
        name: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        created_by_admin_id: int = 0,
        id_on_chain: Optional[int] = None,
        origin: Optional[str] = None,
        current_location: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        condition_id: Optional[int] = None,
        status: str = "active",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Create a new :class:`NFT`.

        Parameters
        ----------
        shared_key : str
            Shared key from the user.
        template_id : int
            ID of the originating :class:`NFTTemplate`.
        prefix : str, optional
            Copy of the template prefix for quick lookup.
        name : str, optional
            Display name of the NFT.
        category : str, optional
            Category label, e.g. "game", "restaurant", "event", etc.
        subcategory : str, optional
            Subcategory label, such as the name of a restaurant or event.
        created_by_admin_id : int, optional
            Admin who created the NFT.
        id_on_chain : int, optional
            Id assigned by the blockchain.
        origin : str, optional
            The NFT's origin on the blockchain.
        current_location : str, optional
            The NFT's current location on the blockchain.
        description : str, optional
            Description of the NFT.
        image_url : str, optional
            URL of the NFT's image.
        condition_id : int, optional
            The :class:`NFTCondition` applied to the NFT.

        status : str, optional
            Lifecycle state (e.g., ``"active"``). Defaults to ``"active"``.
        created_at : datetime, optional
            Explicit creation timestamp.
        updated_at : datetime, optional
            Explicit last update timestamp.
        """
        self.shared_key = shared_key
        self.template_id = template_id
        self.prefix = prefix
        self.name = name
        self.category = category
        self.subcategory = subcategory
        self.created_by_admin_id = created_by_admin_id
        self.id_on_chain = id_on_chain
        self.origin = origin
        self.current_location = current_location
        self.description = description
        self.image_url = image_url
        self.condition_id = condition_id
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    __tablename__ = "nfts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("nft_templates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    prefix: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    id_on_chain: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, unique=True
    )
    origin: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, unique=True
    )
    current_location: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nft_conditions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    template: Mapped[NFTTemplate] = relationship(back_populates="nfts")
    condition: Mapped[Optional[NFTCondition]] = relationship(
        foreign_keys=[condition_id]
    )
    ownerships: Mapped[list["UserNFTOwnership"]] = relationship(back_populates="nft")
    target_cell: Mapped[Optional["BingoCell"]] = relationship(
        back_populates="nft", uselist=False
    )
    chain_txs: Mapped[list["BlockchainTransaction"]] = relationship(
        back_populates="nft"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive','archived')", name="status_enum"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NFT(id={self.id}, template_id={self.template_id}, prefix='{self.prefix}', "
            f"shared_key='{self.shared_key}', status='{self.status}', updated_at={self.updated_at})>"
        )

    # --- utility methods ---
    @classmethod
    def get_by_origin(cls, session: Session, origin: str) -> Optional["NFT"]:
        """Get an NFT object by its ``origin`` field."""

        stmt = select(cls).where(cls.origin == origin)
        return session.scalar(stmt)

    @classmethod
    def count_nfts_by_prefix(cls, session: Session, prefix: str) -> int:
        """Count NFTs that share a given prefix.

        Returns
        -------
        int
            Number of NFTs found.
        """

        stmt = select(func.count()).where(cls.prefix == prefix)
        res = session.scalar(stmt)
        return res or 0

    def count_same_template_nfts(self, session: Session) -> int:
        """Count NFTs that originate from the same template as this NFT.

        Returns
        -------
        int
            Number of NFTs sharing this template.
        """

        stmt = select(func.count()).where(NFT.template_id == self.template_id)
        res = session.scalar(stmt)
        return res or 0

    # --- blockchain integration ---
    def mint_on_chain(
        self,
        session: Session,
        client: Optional["ChainClient"] = None,
        app: Optional[str] = "nict-badge-wallet-sys",
        recipient_paymail: Optional[str] = None,
        file_path: Optional[str] = None,
        additional_info: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Mint this NFT on chain and record a `BlockchainTransaction`.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        client : ChainClient, optional
            Existing `ChainClient`. If omitted, a new one is created.
        app : str, optional
            Application identifier sent to the chain API. Defaults to
            "nict-badge-wallet-sys".
        recipient_paymail : str, optional
            Recipient's paymail.
            If omitted, the NFT on chain will be sent to the current admin's account
            that is set in the `.dotenv` file.
        file_path : str, optional
            Optional path to the NFT's image file. This will be uploaded to the blockchain.
        additional_info : dict[str, Any], optional
            Extra metadata to store on chain.

        Returns
        -------
        dict[str, Any]
            Response from ``ChainClient.create_nft``.

        Notes
        -----
        - This method does not create a local ownership record; call 
        ``User.issue_nft_dbwise`` separately.
        """
        import json
        from nictbw.models.chain import BlockchainTransaction
        from nictbw.blockchain.api import ChainClient

        client = client or ChainClient()

        # Ensure the NFT is persisted so ``session.flush`` will write it to the DB
        if not inspect(self).persistent:
            session.add(self)
            session.flush()

        # Enforce template supply limit
        template = self.template or session.get(NFTTemplate, self.template_id)
        if template is None:
            raise ValueError("NFT template not found")
        if (
            template.max_supply is not None
            and template.minted_count >= template.max_supply
        ):
            raise ValueError("Max supply for this template has been reached")

        # Compose metadata to send alongside mint
        meta: dict[str, Any] = dict(additional_info or {})
        meta.setdefault("prefix", template.prefix)
        meta.setdefault("shared_key", self.shared_key)
        meta.setdefault("category", template.category)
        meta.setdefault("subcategory", template.subcategory)
        if template.description:
            meta.setdefault("description", template.description)
        if template.image_url:
            meta.setdefault("image_url", template.image_url)
        if template.default_condition_id:
            meta.setdefault("condition_id", template.default_condition_id)

        # Prepare client call
        kwargs: dict[str, Any] = {
            "app": app,
            "name": template.name,
            "additional_info": meta,
        }
        if recipient_paymail:
            kwargs["recipient_paymail"] = recipient_paymail
        if file_path:
            kwargs["file_path"] = file_path

        # Call the chain API (normalized response)
        resp: dict = client.create_nft(**kwargs)
        tx_hash: str = resp["transaction_id"]
        nft_information: dict = resp["nft_information"]

        # Update self
        self.update_from_info_on_chain(nft_information)
        if self.template:
            self.template.minted_count += 1

        session.flush()

        # Record blockchain transaction (status 'sent')
        now = datetime.now(timezone.utc)
        tx = BlockchainTransaction(
            user_paymail=recipient_paymail if recipient_paymail else None,
            nft_id=self.id,
            unique_nft_id=f"{template.prefix}_{self.shared_key}",
            type="mint",
            status="sent",
            tx_hash=tx_hash,
            request_payload_json=json.dumps(
                kwargs,
                ensure_ascii=False,
            ),
            response_payload_json=json.dumps(resp, ensure_ascii=False),
            created_at=now,
            confirmed_at=now,
        )
        session.add(tx)
        session.flush()

        return resp

    def update_from_info_on_chain(self, nft_info: dict) -> None:
        """
        Update the NFT instance with information from the blockchain.

        Parameters
        ----------
        nft_info : dict
            The NFT information from the blockchain. Typically obtained
            from Blockchain API responses.
        """
        self.id_on_chain = nft_info.get("nft_id", self.id_on_chain)
        self.origin = nft_info.get("nft_origin", self.origin)
        self.current_location = nft_info.get(
            "current_nft_location", self.current_location
        )
        self.updated_at = datetime.now(timezone.utc)
