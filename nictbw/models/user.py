from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select

from .nft import NFT
from .ownership import UserNFTOwnership
from . import Base

if TYPE_CHECKING:
    from nictbw.blockchain.api import ChainClient
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    def __init__(
        self,
        in_app_id: str,
        paymail: str,
        on_chain_id: Optional[str] = None,
        nickname: Optional[str] = None,
        password_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.in_app_id = in_app_id
        self.paymail = paymail
        self.on_chain_id = on_chain_id
        self.nickname = nickname
        self.password_hash = password_hash
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    in_app_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    paymail: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
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
        back_populates="user"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, in_app_id='{self.in_app_id}', "
            f"nickname='{self.nickname}', on_chain_id='{self.on_chain_id}', updated_at='{self.updated_at}')>"
        )

    @property
    def nfts(self) -> list[NFT]:
        """Get a list of NFTs owned by this user."""
        return [o.nft for o in self.ownerships]

    @classmethod
    def get_by_in_app_id(cls, session: Session, in_app_id: str) -> Optional["User"]:
        """Get user by their in-app ID."""
        return session.scalar(select(cls).where(cls.in_app_id == in_app_id))

    @classmethod
    def get_by_paymail(cls, session: Session, paymail: str) -> Optional["User"]:
        """Get user by their paymail address."""
        return session.scalar(select(cls).where(cls.paymail == paymail))

    @classmethod
    def get_by_on_chain_id(cls, session: Session, on_chain_id: str) -> Optional["User"]:
        """Get user by their on-chain ID."""
        return session.scalar(select(cls).where(cls.on_chain_id == on_chain_id))

    def set_nickname(self, new_nickname: str) -> None:
        """Set user's nickname and update timestamp."""
        self.nickname = new_nickname
        self.updated_at = datetime.now(timezone.utc)

    def set_password_hash(self, new_password_hash: Optional[str]) -> None:
        """Set user's password hash and update timestamp."""
        if new_password_hash is None:
            self.password_hash = None
        else:
            self.password_hash = new_password_hash
        self.updated_at = datetime.now(timezone.utc)

    def verify_password_hash(self, password_hash: str) -> bool:
        """Verify if the provided password hash matches the stored one."""
        return self.password_hash is not None and self.password_hash == password_hash

    def issue_nft_dbwise(self, session: Session, nft: NFT) -> None:
        """
        Issue an NFT to this user in the database. This does not interact with the blockchain.

        Parameters
        ----------
        session : Session
            SQLAlchemy session for database operations
        nft : NFT
            The NFT to issue to this user

        Notes
        -----
        This method creates a new UserNFTOwnership record linking the user to the NFT,
        assigns a serial number based on the current minted count, generates a unique
        NFT ID, and increments the NFT's minted count.
        """
        new_ownership = UserNFTOwnership(
            user_id=self.id,
            nft_id=nft.id,
            serial_number=nft.minted_count,
            unique_nft_id=nft.prefix + "-" + str(nft.minted_count),
            acquired_at=nft.created_at,
        )
        self.ownerships.append(new_ownership)
        nft.minted_count += 1  # Increment the minted count
        session.add(new_ownership)

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
        - Newly seen on-chain NFTs are created in the DB with placeholder fields
          where information is not available on chain.
        - Caller is responsible for managing the outer transaction (commit/rollback).
        """
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

            # Fetch or create the corresponding NFT record
            nft = NFT.get_by_origin(session, origin)
            if nft is None:
                nft = NFT(
                    prefix=item[
                        "nft_origin"
                    ],  # TODO: need confirmation of how to set prefix
                    shared_key=item[
                        "nft_origin"
                    ],  # TODO: need confirmation of shared_key
                    name=item.get("name", "Unnamed NFT"),
                    nft_type=item.get("sub_type", "default"),
                    description="default description",  # TODO: need confirmation of description
                    created_by_admin_id=0,  # TODO: need confirmation of creator admin ID. The value 0 is a placeholder.
                    # We might want to save the information above in the `metadata` field when minting NFTs.
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
                session.add(nft)
                session.flush()

            # Add ownership if not already present
            if origin not in existing_nft_origins:
                session.add(
                    UserNFTOwnership(
                        user_id=self.id,
                        nft_id=nft.id,
                        serial_number=nft.count_same_prefix_nfts(session) + 1,
                        # TODO: confirm if the serial number generation is correct
                        unique_nft_id=origin,  # Using origin as unique NFT ID here. This is a temporary measure.
                        # We need to generate a proper unique NFT ID using its prefix and serial number,
                        # which are not stored on chain for now and thus not available.
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
