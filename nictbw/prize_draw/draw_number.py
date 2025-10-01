"""Helpers for deriving deterministic draw numbers from NFT origins."""

from __future__ import annotations


def _normalize_origin(origin: str) -> str:
    """Normalize origin input before using it directly as the draw number."""

    if origin is None:
        raise ValueError("origin must not be None")
    if not isinstance(origin, str):
        raise TypeError("origin must be a string")
    normalized = origin.strip().lower()
    if not normalized:
        raise ValueError("origin must not be empty")
    return normalized


def derive_draw_number(origin: str) -> str:
    """Return the deterministic draw number for ``origin``."""

    return _normalize_origin(origin)


__all__ = ["derive_draw_number"]
