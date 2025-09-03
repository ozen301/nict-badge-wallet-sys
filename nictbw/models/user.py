from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, select

from nictbw.blockchain.api import ChainClient

from .nft import NFT
from .ownership import UserNFTOwnership
from . import Base

if TYPE_CHECKING:
    from .bingo import BingoCard
    from .chain import BlockchainTransaction


class User(Base):
    def __init__(
        self,
        in_app_id: str,
        wallet: str,
        nickname: Optional[str] = None,
        password_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.in_app_id = in_app_id
        self.wallet = wallet
        self.nickname = nickname
        self.password_hash = password_hash
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    in_app_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    wallet: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
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
            f"nickname='{self.nickname}', updated_at='{self.updated_at}')>"
        )

    @classmethod
    def get_by_in_app_id(cls, session: Session, in_app_id: str) -> User | None:
        """Get user by their in-app ID."""
        return session.scalar(select(cls).where(cls.in_app_id == in_app_id))

    @classmethod
    def get_by_wallet(cls, session: Session, wallet: str) -> User | None:
        """Get user by their wallet address."""
        return session.scalar(select(cls).where(cls.wallet == wallet))

    def set_nickname(self, new_nickname: str) -> None:
        """Set user's nickname and update timestamp."""
        self.nickname = new_nickname
        self.updated_at = datetime.now(timezone.utc)

    def set_password_hash(self, new_password_hash: str | None) -> None:
        """Set user's password hash and update timestamp."""
        if new_password_hash is None:
            self.password_hash = None
        else:
            self.password_hash = new_password_hash
        self.updated_at = datetime.now(timezone.utc)

    def verify_password_hash(self, password_hash: str) -> bool:
        """Verify if the provided password hash matches the stored one."""
        return self.password_hash is not None and self.password_hash == password_hash

    def issue_nft(self, session: Session, nft: NFT) -> None:
        """
        Issue an NFT to this user.

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

    def sync_nfts_from_chain(
        self, session: Session, client: ChainClient | None = None
    ) -> None:
        """Refresh this user's NFT ownership using the blockchain API."""
        client = client or ChainClient()
        chain_items = client.get_user_nfts(self.in_app_id)

        existing_ownerships = {o.unique_nft_id: o for o in self.ownerships}
        nft_origins_on_chain: set[str] = set()

        for item in chain_items:
            unique_id = item["nft_origin"]
            nft_origins_on_chain.add(unique_id)

            # Fetch or create the corresponding NFT record
            nft = NFT.get_by_prefix(session, item["nft_origin"])
            if nft is None:
                nft = NFT(
                    prefix=item["nft_origin"],
                    shared_key=item[
                        "nft_origin"
                    ],  # TODO: need confirmation of shared_key
                    name=item["name"],
                    nft_type=item.get("sub_type") or "default",
                    description=item.get(
                        "metadata"
                    ),  # TODO: need confirmation of description
                    created_by_admin_id=0,  # TODO: need retrieval of creator admin ID
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
                session.add(nft)
                session.flush()

            # Upsert ownership
            if unique_id not in existing_ownerships:
                session.add(
                    UserNFTOwnership(
                        user_id=self.id,
                        nft_id=nft.id,
                        serial_number=nft.count_same_prefix_nfts(session) + 1,
                        unique_nft_id=unique_id,
                        acquired_at=datetime.fromisoformat(item["created_at"]),
                    )
                )

        # Remove stale ownerships
        # TODO: need to confirm if this is necessary
        # for uid, ownership in existing_ownerships.items():
        #     if uid not in nft_origins_on_chain:
        #         session.delete(ownership)

        session.commit()
