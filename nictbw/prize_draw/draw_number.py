"""Helpers for deriving deterministic draw numbers from NFT origins."""

from __future__ import annotations


def _normalize_origin(origin: str) -> str:
    """Normalize a raw NFT `origin` value by trimming and lower-casing.

    Parameters
    ----------
    origin : str
        Raw origin value captured on the NFT.
    """

    if origin is None:
        raise ValueError("origin must not be None")
    if not isinstance(origin, str):
        raise TypeError("origin must be a string")
    normalized = origin.strip().lower()
    if not normalized:
        raise ValueError("origin must not be empty")
    return normalized


def derive_draw_number(origin: str) -> str:
    """Calculate the deterministic draw number for an NFT origin.

    Parameters
    ----------
    origin : str
        The NFT's `origin` string.

    Returns
    -------
    str
        Normalized draw number of the NFT.
    """

    return _normalize_origin(origin)


__all__ = ["derive_draw_number"]
