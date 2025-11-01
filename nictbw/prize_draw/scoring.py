"""Scoring utilities for prize draw evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class ScoreComputation:
    """Raw results returned by a scoring routine."""

    score: float
    draw_top_digits: str
    winning_top_digits: str


@dataclass(frozen=True)
class ScoreEvaluation:
    """Result of evaluating a scoring algorithm.

    Attributes
    ----------
    algorithm_key : str
        Identifier of the algorithm used for evaluation. This matches
        :attr:`ScoringAlgorithm.key`, which is also stored in
        `AlgorithmRegistry._algorithms`.
    score : float
        Similarity score produced by the algorithm.
    threshold : Optional[float]
        Threshold against which ``score`` was compared, if any.
    passed : Optional[bool]
        ``True`` when the score passes the threshold, ``False`` when it fails,
        and ``None`` when no threshold was supplied.
    draw_top_digits : Optional[str]
        Ten-digit representation of the hashed draw number if available.
    winning_top_digits : Optional[str]
        Ten-digit representation of the hashed winning number if available.
    """

    algorithm_key: str
    score: float
    threshold: Optional[float]
    passed: Optional[bool]
    draw_top_digits: Optional[str]
    winning_top_digits: Optional[str]


@dataclass(frozen=True)
class ScoringAlgorithm:
    """Definition of a scoring algorithm.

    Attributes
    ----------
    key : str
        Registry key used to identify the algorithm. This is used by
        :class:`AlgorithmRegistry` to map to the algorithm definition.
    scorer : Callable[[str, str], ScoreComputation]
        Callable that takes the draw number string and winning number string as input
        and returns the similarity score and derived display digits.
    description : Optional[str]
        Human-readable summary of the algorithm's behaviour.
    """

    key: str
    scorer: Callable[[str, str], ScoreComputation]
    description: Optional[str] = None

    def evaluate(
        self,
        draw_number: str,
        winning_number: str,
        threshold: Optional[float] = None,
    ) -> ScoreEvaluation:
        """Calculate the similarity score and returns the result.

        Parameters
        ----------
        draw_number : str
            Normalized draw number derived from the NFT.
        winning_number : str
            Reference value representing the winning draw.
        threshold : Optional[float], default: None
            Threshold applied to ``score`` for pass/fail classification.

        Returns
        -------
        ScoreEvaluation
            Dataclass describing the evaluation result.
        """
        computation = self.scorer(draw_number, winning_number)
        score = float(computation.score)
        passed = None if threshold is None else score >= threshold
        return ScoreEvaluation(
            algorithm_key=self.key,
            score=score,
            threshold=threshold,
            passed=passed,
            draw_top_digits=computation.draw_top_digits,
            winning_top_digits=computation.winning_top_digits,
        )


class AlgorithmRegistry:
    """Mutable registry mapping algorithm keys to definitions."""

    def __init__(self) -> None:
        self._algorithms: Dict[str, ScoringAlgorithm] = {}

    def register(self, algorithm: ScoringAlgorithm, *, replace: bool = False) -> None:
        """Register a scoring algorithm under its key.

        This stores the algorithm in the registry's internal mapping using
        ``algorithm.key``, so that it can be retrieved later and used for
        evaluation.

        Parameters
        ----------
        algorithm : ScoringAlgorithm
            Algorithm to add to the registry.
        replace : bool, default: False
            When ``True`` an existing registration with the same key is
            overwritten. Otherwise a duplicate raises :class:`ValueError`.
        """
        if not replace and algorithm.key in self._algorithms:
            raise ValueError(f"Algorithm '{algorithm.key}' is already registered")
        self._algorithms[algorithm.key] = algorithm

    def get(self, key: str) -> ScoringAlgorithm:
        """Return the algorithm registered under ``key``."""
        try:
            return self._algorithms[key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Unknown scoring algorithm '{key}'") from exc

    def evaluate(
        self,
        key: str,
        draw_number: str,
        winning_number: str,
        *,
        threshold: Optional[float] = None,
    ) -> ScoreEvaluation:
        """Evaluate a draw using the algorithm referenced by ``key``.

        Parameters
        ----------
        key : str
            Identifier of the algorithm to execute.
        draw_number : str
            Draw number of the NFT.
        winning_number : str
            Winning number to compare against.
        threshold : Optional[float], default: None
            Threshold supplied to the algorithm.

        Returns
        -------
        ScoreEvaluation
            Evaluation result returned by the selected algorithm.
        """
        algorithm = self.get(key)
        return algorithm.evaluate(draw_number, winning_number, threshold)

    def available_algorithms(self) -> Dict[str, ScoringAlgorithm]:
        """Return a copy of the registered algorithms keyed by identifier."""
        return dict(self._algorithms)


def _sha256_hexdigest(value: str) -> str:
    """Return the SHA-256 hex digest of ``value`` encoded as ASCII."""
    try:
        payload = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "draw and winning numbers must contain only ASCII characters"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _extract_top_digits(value: int, *, digits: int = 10) -> str:
    """Return the leftmost ``digits`` after scaling down by 10**67."""
    scaled = value // 10**67
    text = str(scaled)
    if len(text) > digits:
        text = text[:digits]
    return text.zfill(digits)


def _sha256_hex_similarity(draw_number: str, winning_number: str) -> ScoreComputation:
    """Score similarity by SHA-256 hashing and measuring hex proximity."""
    hashed_left = _sha256_hexdigest(draw_number)
    hashed_right = _sha256_hexdigest(winning_number)

    if len(hashed_left) != len(hashed_right):
        raise ValueError("hashed draw and winning numbers must be the same length")

    left_int = int(hashed_left, 16)
    right_int = int(hashed_right, 16)
    diff = abs(left_int - right_int)

    max_value = (1 << (len(hashed_left) * 4)) - 1
    if max_value <= 0:
        draw_top_digits = _extract_top_digits(left_int)
        winning_top_digits = _extract_top_digits(right_int)
        return ScoreComputation(
            score=1.0,
            draw_top_digits=draw_top_digits,
            winning_top_digits=winning_top_digits,
        )

    similarity = (0.6 - (diff / max_value)) * 1.5
    if similarity < 0.0:
        similarity = 0.0
    if similarity > 1.0:
        similarity = 1.0
    draw_top_digits = _extract_top_digits(left_int)
    winning_top_digits = _extract_top_digits(right_int)
    return ScoreComputation(
        score=float(similarity),
        draw_top_digits=draw_top_digits,
        winning_top_digits=winning_top_digits,
    )


DEFAULT_SCORING_REGISTRY = AlgorithmRegistry()
DEFAULT_SCORING_REGISTRY.register(
    ScoringAlgorithm(
        key="sha256_hex_proximity",
        scorer=_sha256_hex_similarity,
        description=(
            "SHA-256 hash inputs, interpret the hex digests as 256-bit integers, and "
            "return a 0.0–1.0 similarity score based on the normalized inverse "
            "absolute difference."
        ),
    )
)
__all__ = [
    "AlgorithmRegistry",
    "DEFAULT_SCORING_REGISTRY",
    "ScoreComputation",
    "ScoreEvaluation",
    "ScoringAlgorithm",
]
