"""Utility helpers for the models package."""

from __future__ import annotations

import secrets
import string
from typing import Optional
from sqlalchemy.orm import Session

BASE62_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase


def generate_unique_instance_id(
    prefix: str,
    session: Optional[Session] = None,
    length: int = 12,
    max_attempts: int = 32,
) -> str:
    """Return a unique NFT-instance identifier using base62 random characters.

    When a session is provided, the helper retries if the generated value is
    already present (or pending) in ``NFTInstance.unique_instance_id``.
    """

    ownership_cls = None
    select_stmt = None
    if session is not None:
        from sqlalchemy import select
        from .ownership import NFTInstance

        ownership_cls = NFTInstance
        select_stmt = select

    attempts = 0
    while attempts < max_attempts:
        suffix = "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))
        candidate = f"{prefix}-{suffix}"[:255]

        if session is not None and ownership_cls is not None and select_stmt is not None:
            collision = False
            for obj in session.new:
                if isinstance(obj, ownership_cls) and getattr(obj, "unique_instance_id", None) == candidate:
                    collision = True
                    break
            if collision:
                attempts += 1
                continue

            exists = session.scalar(
                select_stmt(ownership_cls.id).where(ownership_cls.unique_instance_id == candidate)
            )
            if exists is not None:
                attempts += 1
                continue

        return candidate

    raise RuntimeError(
        "Unable to generate a unique NFT-instance identifier after multiple attempts"
    )
