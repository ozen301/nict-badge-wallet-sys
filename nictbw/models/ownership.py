from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    select,
)
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .nft import NFT
    from .bingo import BingoCell
    from .coupon import CouponInstance


class UserNFTOwnership(Base):
    """Association table recording which user owns which NFT."""

    def __init__(
        self,
        user_id: int,
        nft_id: int,
        serial_number: int,
        unique_nft_id: str,
        acquired_at: datetime,
        other_meta: Optional[str] = None,
    ):
        """Create a new ownership record.

        Parameters
        ----------
        user_id : int
            Owning user's ID.
        nft_id : int
            ID of the owned NFT.
        serial_number : int
            Serial number of this NFT within those minted from the same template.
        unique_nft_id : str
            Unique identifier for the NFT. The format is f"{nft.prefix}_{nft.shared_key}".
        acquired_at : datetime
            When the user acquired the NFT.
        other_meta : str, optional
            Additional metadata encoded as JSON string.
        """

        self.user_id = user_id
        self.nft_id = nft_id
        self.serial_number = serial_number
        self.unique_nft_id = unique_nft_id
        self.acquired_at = acquired_at
        self.other_meta = other_meta

    __tablename__ = "user_nft_ownership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nft_id: Mapped[int] = mapped_column(
        ForeignKey("nfts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_nft_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    other_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ownerships")
    nft: Mapped["NFT"] = relationship(back_populates="ownerships")
    matched_cells: Mapped[list["BingoCell"]] = relationship(
        back_populates="matched_ownership"
    )
    coupon_instances: Mapped[list["CouponInstance"]] = relationship(
        "CouponInstance",
        back_populates="ownership",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "nft_id", name="uq_user_nft"),
        UniqueConstraint("nft_id", "serial_number", name="uq_nft_serial"),
        Index("ix_unique_nft_id", "unique_nft_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserNFTOwnership(id={self.id}, user_id={self.user_id}, "
            f"nft_id={self.nft_id}, acquired_at={self.acquired_at})>"
        )

    @classmethod
    def get_by_user_and_nft(
        cls,
        session: Session,
        user: "User | int",
        nft: "NFT | int",
    ) -> Optional["UserNFTOwnership"]:
        """Retrieve ownership record linking ``user`` to ``nft``.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session.
        user : User | int
            The owning user or their primary key. Can be a ``User`` instance or its primary key.
        nft : NFT | int
            NFT whose ownership is queried, or its primary key. Can be an ``NFT`` instance or its primary key.

        Returns
        -------
        Optional[UserNFTOwnership]
            The matching ownership or ``None`` if not owned.
        """

        def _to_id(obj: "int | User | NFT") -> int:
            return obj if isinstance(obj, int) else obj.id

        user_id = _to_id(user)
        nft_id = _to_id(nft)
        return session.scalar(
            select(cls).where(cls.user_id == user_id, cls.nft_id == nft_id)
        )
