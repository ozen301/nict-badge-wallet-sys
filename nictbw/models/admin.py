from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column, validates

from .base import Base
from .id_type import ID_TYPE


class Admin(Base):
    """Admin account model aligned with API schema."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, index=True, autoincrement=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @classmethod
    def get_by_email(cls, session: Session, email: str) -> Optional["Admin"]:
        """Get admin by their email address."""
        return session.query(cls).filter(cls.email == email).one_or_none()

    @classmethod
    def get_by_paymail(cls, session: Session, paymail: str) -> Optional["Admin"]:
        """Backward-compatible alias that maps to email lookup."""
        return cls.get_by_email(session, paymail)

