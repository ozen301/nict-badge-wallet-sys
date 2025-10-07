"""Scoring utilities for prize draw evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


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
    """

    algorithm_key: str
    score: float
    threshold: Optional[float]
    passed: Optional[bool]


@dataclass(frozen=True)
class ScoringAlgorithm:
    """Definition of a scoring algorithm.

    Attributes
    ----------
    key : str
        Registry key used to identify the algorithm. This is used by
        :class:`AlgorithmRegistry` to map to the algorithm definition.
    scorer : Callable[[str, str], float]
        Callable that takes the draw number string and winning number string as input
        and returns a similarity score as a float. The score is typically in the range
        [0.0, 1.0], but this is not enforced.
    description : Optional[str]
        Human-readable summary of the algorithm's behaviour.
    """

    key: str
    scorer: Callable[[str, str], float]
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
        score = float(self.scorer(draw_number, winning_number))
        passed = None if threshold is None else score >= threshold
        return ScoreEvaluation(
            algorithm_key=self.key,
            score=score,
            threshold=threshold,
            passed=passed,
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


def _hamming_similarity(draw_number: str, winning_number: str) -> float:
    """Compute normalized Hamming similarity for two ASCII strings.

    This function converts both input strings to ASCII-encoded bytes and
    compares them bitwise. If the inputs are of unequal length, the shorter
    one is padded with zero bytes (``b'\x00'``) on the right to match the
    length of the longer one.

    Returns
    -------
    float
        Similarity score in the inclusive range [0.0, 1.0].
    """
    try:
        left: bytes = draw_number.encode("ascii")
        right: bytes = winning_number.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "draw and winning numbers must contain only ASCII characters"
        ) from exc

    if not left and not right:
        return 1.0

    max_len = max(len(left), len(right))
    padded_left = left.ljust(max_len, b"\x00")
    padded_right = right.ljust(max_len, b"\x00")
    xor_result = int.from_bytes(padded_left, "big") ^ int.from_bytes(
        padded_right, "big"
    )
    distance_bits = xor_result.bit_count()
    total_bits = max_len * 8
    similarity = 1.0 - (distance_bits / total_bits)
    if similarity < 0.0:
        return 0.0
    if similarity > 1.0:
        return 1.0
    return float(similarity)


DEFAULT_SCORING_REGISTRY = AlgorithmRegistry()
DEFAULT_SCORING_REGISTRY.register(
    ScoringAlgorithm(
        key="hamming",
        scorer=_hamming_similarity,
        description=(
            "Normalized character-wise similarity using bit-level comparisons "
            "with zero padding for unequal lengths. Scores range from 0.0 (no "
            "overlap) to 1.0 (perfect match)."
        ),
    )
)
__all__ = [
    "AlgorithmRegistry",
    "DEFAULT_SCORING_REGISTRY",
    "ScoreEvaluation",
    "ScoringAlgorithm",
]
