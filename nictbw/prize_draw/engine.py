"""Workflow engine for evaluating prize draws against NFT instances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .draw_number import derive_draw_number
from .scoring import AlgorithmRegistry, DEFAULT_SCORING_REGISTRY
from ..models import PrizeDrawResult, PrizeDrawType, PrizeDrawWinningNumber
from ..models.ownership import NFTInstance


@dataclass
class PrizeDrawEvaluation:
    """Value object describing an evaluation produced by the engine.

    Attributes
    ----------
    result : PrizeDrawResult
        The draw outcome stored in the database.
    draw_number : str
        Normalized draw number derived from the NFT instance origin.
    threshold : Optional[float]
        Threshold used when comparing against the winning number.
    similarity : Optional[float]
        Algorithm-dependent similarity score; ``None`` when pending.
    """

    result: PrizeDrawResult
    draw_number: str
    threshold: Optional[float]
    similarity: Optional[float]


class PrizeDrawEngine:
    """Engine that manages draw number derivation, scoring, and result persistence."""

    def __init__(
        self,
        session: Session,
        *,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> None:
        """Create an prize draw engine bound to a SQLAlchemy session.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session used for lookups and persistence.
        registry : Optional[AlgorithmRegistry], default: None
            Custom scoring registry that contains scoring algorithms.
            Typically this parameter is omitted, in which case the default
            registry will be used.
        """

        self._session = session
        self._registry = registry or DEFAULT_SCORING_REGISTRY

    def evaluate(
        self,
        nft_instance: NFTInstance,
        draw_type: PrizeDrawType,
        winning_number: Optional[PrizeDrawWinningNumber] = None,
        threshold: Optional[float] = None,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> PrizeDrawEvaluation:
        """Evaluate ``nft_instance`` against a winning number and persist the result.

        Parameters
        ----------
        nft_instance : NFTInstance
            NFT instance to evaluate. ``nft_origin`` is required for draw number derivation.
        draw_type : PrizeDrawType
            Draw configuration describing algorithm and default threshold.
        winning_number : Optional[PrizeDrawWinningNumber], default: None
            Winning reference to compare against. When omitted, the result is
            stored with a ``"pending"`` outcome.
        threshold : Optional[float], default: None
            Override the threshold used by the scoring algorithm when provided.
            If not provided, the draw type's ``default_threshold`` will be used.
        registry : Optional[AlgorithmRegistry], default: None
            Registry containing the scoring algorithms to use.
            Typically, this field is omitted, in which case the default registry
            defined in :class:`PrizeDrawEngine` is used.

        Returns
        -------
        PrizeDrawEvaluation
            `PrizeDrawEvaluation` object that holds the result, draw_number,
            threshold, and similarity score (if applicable).

        Notes
        -----
        This evaluation process performs the following steps:

        1. Validate the supplied :class:`NFTInstance`.
        2. Derive the deterministic draw number from the instance's ``nft_origin``.
        3. Run the scoring algorithm (when a winning number is provided) and
           save the result (in "win", "lose", or "pending" string format)
           expected by the database model.
        4. Upsert the :class:`PrizeDrawResult` row.


        Raises
        ------
        ValueError
            If the NFT instance or draw type prerequisites are unmet.
        """
        if nft_instance.id is None:
            raise ValueError("NFT instance must be persisted before running a prize draw")
        if draw_type.id is None:
            raise ValueError("Draw type must be persisted before running a prize draw")
        if nft_instance.user_id is None:
            raise ValueError("NFT instance must have a user_id")
        if nft_instance.definition_id is None:
            raise ValueError("NFT instance must have a definition_id")
        if nft_instance.nft_origin is None:
            raise ValueError("NFT instance must have an nft_origin before running a prize draw")

        draw_number = derive_draw_number(nft_instance.nft_origin)

        threshold_to_use = (
            threshold if threshold is not None else draw_type.default_threshold
        )

        evaluation_similarity: Optional[float] = None
        evaluation_draw_digits: Optional[str] = None
        evaluation_winning_digits: Optional[str] = None
        outcome = "pending"

        # Only run the evaluation if a winning number is provided.  This
        # allows callers to "pre-register" instances for a draw before the winning
        # number is known.
        if winning_number is not None:
            active_registry = registry or self._registry
            algorithm = active_registry.get(draw_type.algorithm_key)
            evaluation = algorithm.evaluate(
                draw_number,
                winning_number.value,
                threshold=threshold_to_use,
            )
            evaluation_similarity = evaluation.score
            evaluation_draw_digits = evaluation.draw_top_digits
            evaluation_winning_digits = evaluation.winning_top_digits
            if evaluation.passed is True:
                outcome = "win"
            elif evaluation.passed is False:
                outcome = "lose"

        # Upsert the ``PrizeDrawResult`` row before mutating fields so that a
        # previously persisted record will be updated in-place instead of
        # creating a duplicate row.
        now = datetime.now(timezone.utc)
        result = self._upsert_result(
            nft_instance=nft_instance,
            draw_type=draw_type,
            winning_number=winning_number,
            draw_number=draw_number,
            similarity_score=evaluation_similarity,
            draw_top_digits=evaluation_draw_digits,
            winning_top_digits=evaluation_winning_digits,
            threshold_used=threshold_to_use,
            outcome=outcome,
            evaluated_at=now,
        )

        # Persist the changes so that the caller can inspect the returned ORM
        # object with all attributes populated (especially useful in tests).
        self._session.flush()
        return PrizeDrawEvaluation(
            result=result,
            draw_number=draw_number,
            threshold=threshold_to_use,
            similarity=evaluation_similarity,
        )

    def evaluate_batch(
        self,
        *,
        instances: Iterable[NFTInstance],
        draw_type: PrizeDrawType,
        winning_number: Optional[PrizeDrawWinningNumber] = None,
        threshold: Optional[float] = None,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> list[PrizeDrawEvaluation]:
        """Evaluate multiple NFT instances with a shared configuration.

        The helper delegates to :meth:`PrizeDrawEngine.evaluate` in a loop,
        collecting the results into a list for the caller. This is primarily useful
        for batch processing scenarios where multiple instances need to be evaluated
        with the same configuration.

        Parameters
        ----------
        instances : Iterable[NFTInstance]
            Collection of NFT instances to evaluate against the draw configuration.
        draw_type : PrizeDrawType
            Draw type applied to every evaluation, which determines the algorithm and
            default threshold.
        winning_number : Optional[PrizeDrawWinningNumber], default: None
            Winning number shared across the evaluations, if available.
        threshold : Optional[float], default: None
            Threshold override applied to each evaluation. If not provided, the draw type's
            default threshold will be used.
        registry : Optional[AlgorithmRegistry], default: None
            Optional registry override that contains custom scoring algorithms.

        Returns
        -------
        list[PrizeDrawEvaluation]
            List containing the evaluation metadata for each instance processed.
        """

        evaluations: list[PrizeDrawEvaluation] = []
        for instance in instances:
            evaluations.append(
                self.evaluate(
                    nft_instance=instance,
                    draw_type=draw_type,
                    winning_number=winning_number,
                    threshold=threshold,
                    registry=registry,
                )
            )
        return evaluations

    def _upsert_result(
        self,
        *,
        nft_instance: NFTInstance,
        draw_type: PrizeDrawType,
        winning_number: Optional[PrizeDrawWinningNumber],
        draw_number: str,
        similarity_score: Optional[float],
        draw_top_digits: Optional[str],
        winning_top_digits: Optional[str],
        threshold_used: Optional[float],
        outcome: str,
        evaluated_at: datetime,
    ) -> PrizeDrawResult:
        """Fetch or create the ``PrizeDrawResult`` row and apply the latest fields.

        Parameters
        ----------
        nft_instance : NFTInstance
            NFT instance associated with the evaluation.
        draw_type : PrizeDrawType
            `PrizeDrawType` object to be used for the evaluation, which determines
            the scoring algorithm and the default threshold.
        winning_number : Optional[PrizeDrawWinningNumber]
            Winning number applied to the evaluation, if available.
        draw_number : str
            Normalized draw number computed for the NFT instance.
        similarity_score : Optional[float]
            Result of the scoring algorithm, if available.
        draw_top_digits : Optional[str]
            Ten-digit summary of the hashed draw number, when evaluated.
        winning_top_digits : Optional[str]
            Ten-digit summary of the hashed winning number, when evaluated.
        threshold_used : Optional[float]
            Threshold applied when determining win/lose outcomes.
        outcome : str
            Outcome persisted to the database (in ``"win"``, ``"lose"``, or ``"pending"`` string format).
        evaluated_at : datetime
            Timestamp representing when the evaluation was performed.

        Returns
        -------
        PrizeDrawResult
            The upserted ORM entity with updated fields.
        """

        # Prefer reusing the row for the specific NFT instance. If none exists we
        # fall back to schema-compatible uniqueness on (nft_id, draw_type_id).
        # This keeps the write path stable until the DB constraint is updated.
        result = self._session.scalar(
            select(PrizeDrawResult).where(
                PrizeDrawResult.instance_id == nft_instance.id,
                PrizeDrawResult.draw_type_id == draw_type.id,
            )
        )
        result_by_definition = self._session.scalar(
            select(PrizeDrawResult).where(
                PrizeDrawResult.definition_id == nft_instance.definition_id,
                PrizeDrawResult.draw_type_id == draw_type.id,
            )
        )
        if result is None and result_by_definition is not None:
            if (
                result_by_definition.instance_id is not None
                and result_by_definition.instance_id != nft_instance.id
            ):
                raise ValueError(
                    "Cannot persist prize draw results for multiple NFT instances "
                    "sharing the same definition with the current schema "
                    "constraint (nft_id, draw_type_id). Migrate to an "
                    "instance-based uniqueness constraint to evaluate all instances."
                )
            result = result_by_definition

        if result is None:
            result = PrizeDrawResult(
                draw_type_id=draw_type.id,
                winning_number_id=(
                    winning_number.id if winning_number is not None else None
                ),
                user_id=nft_instance.user_id,
                definition_id=nft_instance.definition_id,
                instance_id=nft_instance.id,
                draw_number=draw_number,
                similarity_score=similarity_score,
                draw_top_digits=draw_top_digits,
                winning_top_digits=winning_top_digits,
                threshold_used=threshold_used,
                outcome=outcome,
                evaluated_at=evaluated_at,
            )
            self._session.add(result)
        else:
            result.winning_number_id = (
                winning_number.id if winning_number is not None else None
            )
            result.user_id = nft_instance.user_id
            result.definition_id = nft_instance.definition_id
            result.instance_id = nft_instance.id
            result.draw_number = draw_number
            result.similarity_score = similarity_score
            result.draw_top_digits = draw_top_digits
            result.winning_top_digits = winning_top_digits
            result.threshold_used = threshold_used
            result.outcome = outcome
            result.evaluated_at = evaluated_at

        return result


__all__ = [
    "PrizeDrawEngine",
    "PrizeDrawEvaluation",
]
