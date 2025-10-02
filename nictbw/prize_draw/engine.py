"""Workflow engine for evaluating prize draws.

The engine focuses on three responsibilities:
* derive the deterministic draw number for an NFT;
* compute the score/outcome using the pluggable scoring registry; and
* persist the resulting :class:`PrizeDrawResult` record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .draw_number import derive_draw_number
from .scoring import AlgorithmRegistry, DEFAULT_SCORING_REGISTRY
from ..models import (
    PrizeDrawOutcome,
    PrizeDrawResult,
    PrizeDrawType,
    PrizeDrawWinningNumber,
)
from ..models.nft import NFT
from ..models.ownership import UserNFTOwnership


@dataclass
class PrizeDrawEvaluation:
    """Value object describing an evaluation produced by the engine."""

    result: PrizeDrawResult
    draw_number: str
    threshold: Optional[float]
    score: Optional[float]


class PrizeDrawEngine:
    """Engine that manages draw number derivation, scoring, and result persistence."""

    def __init__(
        self,
        session: Session,
        *,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> None:
        self._session = session
        self._registry = registry or DEFAULT_SCORING_REGISTRY

    def evaluate(
        self,
        *,
        nft: NFT,
        draw_type: PrizeDrawType,
        winning_number: Optional[PrizeDrawWinningNumber] = None,
        threshold: Optional[float] = None,
        algorithm_version: Optional[str] = None,
        payload: Optional[dict[str, Any] | str] = None,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> PrizeDrawEvaluation:
        """Evaluate ``nft`` against ``winning_number`` and persist the result.

        If ``winning_number`` is ``None``, the evaluation will be recorded with a
        :attr:`PrizeDrawOutcome.PENDING` outcome, allowing callers to "pre-register"
        the evaluation.

        The evaluation process performs the following steps:

        1. Resolve the most recent :class:`UserNFTOwnership`
           record to capture which user owned the NFT at evaluation time.
        2. Derive the deterministic draw number from the NFT origin.
        3. Run the scoring algorithm (when a winning number is provided) and
           translate the returned verdict into the :class:`PrizeDrawOutcome`
           enum expected by the database model.
        4. Upsert the :class:`PrizeDrawResult` row.

        The method returns a :class:`PrizeDrawEvaluation` containing both the
        ORM result object and the computed values for further inspection.
        """

        if nft.id is None:
            raise ValueError("NFT must be persisted before running a prize draw")
        if nft.origin is None:
            raise ValueError("NFT must have an origin before running a prize draw")
        if draw_type.id is None:
            raise ValueError("Draw type must be persisted before running a prize draw")

        ownership = self._resolve_latest_ownership(nft)
        if ownership is None:
            raise ValueError("NFT has no ownership record and cannot be evaluated")

        draw_number = derive_draw_number(nft.origin)

        threshold_to_use = (
            threshold if threshold is not None else draw_type.default_threshold
        )

        evaluation_score: Optional[float] = None
        outcome = PrizeDrawOutcome.PENDING

        # Only run the evaluation if a winning number is provided.  This
        # allows callers to "pre-register" NFTs for a draw before the winning
        # number is known.
        if winning_number is not None:
            active_registry = registry or self._registry
            algorithm = active_registry.get(draw_type.algorithm_key)
            evaluation = algorithm.evaluate(
                draw_number,
                winning_number.value,
                threshold=threshold_to_use,
            )
            evaluation_score = evaluation.score
            if evaluation.passed is True:
                outcome = PrizeDrawOutcome.WIN
            elif evaluation.passed is False:
                outcome = PrizeDrawOutcome.LOSE

        # Serialize the payload to a string for storage in the ``notes`` field, if provided.
        payload_notes: Optional[str]
        if payload is None:
            payload_notes = None
        elif isinstance(payload, str):
            payload_notes = payload
        else:
            import json

            payload_notes = json.dumps(payload, sort_keys=True)

        # Upsert the ``PrizeDrawResult`` row before mutating fields so that a
        # previously persisted record will be updated in-place instead of
        # creating a duplicate row.
        now = datetime.now(timezone.utc)
        result = self._upsert_result(
            nft=nft,
            draw_type=draw_type,
            winning_number=winning_number,
            user_id=ownership.user_id,
            ownership_id=ownership.id,
            draw_number=draw_number,
            distance_score=evaluation_score,
            threshold_used=threshold_to_use,
            outcome=outcome,
            algorithm_version=algorithm_version,
            evaluated_at=now,
            notes=payload_notes,
        )

        # Persist the changes so that the caller can inspect the returned ORM
        # object with all attributes populated (especially useful in tests).
        self._session.flush()
        return PrizeDrawEvaluation(
            result=result,
            draw_number=draw_number,
            threshold=threshold_to_use,
            score=evaluation_score,
        )

    def _resolve_latest_ownership(self, nft: NFT) -> Optional[UserNFTOwnership]:
        """Return the newest ownership snapshot for ``nft`` if one exists."""

        # Ordering by ``acquired_at`` (then ``id``) gives us a deterministic
        # "latest" record even when timestamps collide due to database
        # precision.
        stmt = (
            select(UserNFTOwnership)
            .where(UserNFTOwnership.nft_id == nft.id)
            .order_by(UserNFTOwnership.acquired_at.desc(), UserNFTOwnership.id.desc())
        )
        return self._session.scalars(stmt).first()

    def _upsert_result(
        self,
        *,
        nft: NFT,
        draw_type: PrizeDrawType,
        winning_number: Optional[PrizeDrawWinningNumber],
        user_id: int,
        ownership_id: int,
        draw_number: str,
        distance_score: Optional[float],
        threshold_used: Optional[float],
        outcome: PrizeDrawOutcome,
        algorithm_version: Optional[str],
        evaluated_at: datetime,
        notes: Optional[str],
    ) -> PrizeDrawResult:
        """Fetch or create the ``PrizeDrawResult`` row and apply the latest fields."""

        # The prize draw results table enforces a uniqueness constraint on the
        # ``(nft_id, draw_type_id)`` tuple.  We emulate the
        # same lookup here so that re-running a draw simply updates the existing
        # row rather than attempting to insert a duplicate.
        stmt = select(PrizeDrawResult).where(
            PrizeDrawResult.nft_id == nft.id,
            PrizeDrawResult.draw_type_id == draw_type.id,
        )

        result = self._session.scalars(stmt).first()
        if result is None:
            result = PrizeDrawResult(
                draw_type_id=draw_type.id,
                winning_number_id=(
                    winning_number.id if winning_number is not None else None
                ),
                user_id=user_id,
                nft_id=nft.id,
                ownership_id=ownership_id,
                draw_number=draw_number,
                distance_score=distance_score,
                threshold_used=threshold_used,
                outcome=outcome,
                algorithm_version=algorithm_version,
                evaluated_at=evaluated_at,
                notes=notes,
            )
            self._session.add(result)
        else:
            result.winning_number_id = (
                winning_number.id if winning_number is not None else None
            )
            result.user_id = user_id
            result.ownership_id = ownership_id
            result.draw_number = draw_number
            result.distance_score = distance_score
            result.threshold_used = threshold_used
            result.outcome = outcome
            result.algorithm_version = algorithm_version
            result.evaluated_at = evaluated_at
            result.notes = notes

        return result


def evaluate_batch(
    engine: PrizeDrawEngine,
    *,
    nfts: Iterable[NFT],
    draw_type: PrizeDrawType,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    threshold: Optional[float] = None,
    algorithm_version: Optional[str] = None,
    payload: Optional[dict[str, Any] | str] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> list[PrizeDrawEvaluation]:
    """Convenience helper to evaluate multiple NFTs with a shared configuration.

    The helper mostly delegates to :meth:`PrizeDrawEngine.evaluate` in a loop,
    collecting the results into a list for the caller.  This is primarily useful
    for batch processing scenarios where multiple NFTs need to be evaluated
    with the same configuration.
    """

    evaluations: list[PrizeDrawEvaluation] = []
    for nft in nfts:
        evaluations.append(
            engine.evaluate(
                nft=nft,
                draw_type=draw_type,
                winning_number=winning_number,
                threshold=threshold,
                algorithm_version=algorithm_version,
                payload=payload,
                registry=registry,
            )
        )
    return evaluations


__all__ = [
    "PrizeDrawEngine",
    "PrizeDrawEvaluation",
    "evaluate_batch",
]
