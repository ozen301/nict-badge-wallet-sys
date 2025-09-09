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
    select,
    func,
)
from . import Base

if TYPE_CHECKING:
    from .ownership import UserNFTOwnership
    from .bingo import BingoCell
    from .chain import BlockchainTransaction
    from nictbw.blockchain.api import ChainClient


class NFTCondition(Base):
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
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    location_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    prohibited_nft_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nfts.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    other_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
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


class NFT(Base):
    def __init__(
        self,
        prefix: str,
        shared_key: str,
        name: str,
        nft_type: str,
        created_by_admin_id: int,
        id_on_chain: Optional[int] = None,
        origin: Optional[str] = None,
        current_location: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        condition_id: Optional[int] = None,
        max_supply: Optional[int] = None,
        minted_count: int = 0,
        status: str = "active",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.prefix = prefix
        self.shared_key = shared_key
        self.name = name
        self.nft_type = nft_type
        self.created_by_admin_id = created_by_admin_id
        self.id_on_chain = id_on_chain
        self.origin = origin
        self.current_location = current_location
        self.description = description
        self.image_url = image_url
        self.condition_id = condition_id
        self.max_supply = max_supply
        self.minted_count = minted_count
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    __tablename__ = "nfts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    shared_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    nft_type: Mapped[str] = mapped_column(String(50), nullable=False)
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
    max_supply: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    condition: Mapped[Optional[NFTCondition]] = relationship(
        foreign_keys=[condition_id]
    )
    ownerships: Mapped[list["UserNFTOwnership"]] = relationship(back_populates="nft")
    target_cells: Mapped[list["BingoCell"]] = relationship(back_populates="target_nft")
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
            f"<NFT(id={self.id}, prefix='{self.prefix}', shared_key='{self.shared_key}', "
            f"name='{self.name}', condition_id={self.condition_id}, updated_at={self.updated_at})>"
        )

    # --- utility methods ---
    @classmethod
    def get_by_origin(cls, session: Session, origin: str) -> Optional["NFT"]:
        """Get the NFT with the specified origin."""
        stmt = select(cls).where(cls.origin == origin)
        return session.scalar(stmt)

    @classmethod
    def count_nfts_by_prefix(cls, session: Session, prefix: str) -> int:
        """Get the count of NFTs with the specified prefix."""
        stmt = select(func.count()).where(cls.prefix == prefix)
        res = session.scalar(stmt)
        return res or 0

    @classmethod
    def get_by_prefix(cls, session: Session, prefix: str) -> Optional["NFT"]:
        """Get the first NFT with the specified prefix."""
        stmt = select(cls).where(cls.prefix == prefix)
        return session.scalar(stmt)

    def count_same_prefix_nfts(self, session: Session) -> int:
        """Get the count of NFTs with the same prefix as this NFT."""
        return NFT.count_nfts_by_prefix(session, self.prefix)

    # --- blockchain integration ---
    def mint_on_chain(
        self,
        session: Session,
        client: Optional["ChainClient"] = None,
        *,
        app: str,
        recipient_paymail: Optional[str] = None,
        file_path: Optional[str] = None,
        additional_info: Optional[dict] = None,
    ) -> dict:
        """
        Mint this NFT on chain via ChainClient and record a BlockchainTransaction.

        Notes
        -----
        - Does not assign ownership in the DB. Use User.issue_nft_dbwise for that.
        - Returns the created BlockchainTransaction. Caller controls commit.
        """
        import json
        from nictbw.models.chain import BlockchainTransaction
        from nictbw.blockchain.api import ChainClient

        client = client or ChainClient()

        # Compose metadata to send alongside mint
        meta: dict[str, Any] = dict(additional_info or {})
        meta.setdefault("prefix", self.prefix)
        meta.setdefault("shared_key", self.shared_key)
        meta.setdefault("nft_type", self.nft_type)
        if self.description:
            meta.setdefault("description", self.description)
        if self.image_url:
            meta.setdefault("image_url", self.image_url)
        if self.condition_id:
            meta.setdefault("condition_id", self.condition_id)

        # Prepare client call
        kwargs: dict[str, Any] = {
            "app": app,
            "name": self.name,
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

        session.flush()

        # Record blockchain transaction (status 'sent')
        now = datetime.now(timezone.utc)
        tx = BlockchainTransaction(
            user_id=None,
            nft_id=self.id,
            unique_nft_id=f"{self.prefix}_{self.shared_key}",
            type="mint",
            status="sent",
            tx_hash=tx_hash,
            request_payload_json=json.dumps(
                {
                    "app": app,
                    "name": self.name,
                    "recipient_paymail": recipient_paymail,
                    "additional_info": meta,
                },
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
