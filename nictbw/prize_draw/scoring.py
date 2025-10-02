"""Scoring utilities for prize draw evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class ScoreEvaluation:
    """Result of evaluating a scoring algorithm."""

    algorithm_key: str
    score: float
    threshold: Optional[float]
    passed: Optional[bool]


@dataclass(frozen=True)
class ScoringAlgorithm:
    """Definition of a scoring algorithm."""

    key: str
    scorer: Callable[[str, str], float]
    description: Optional[str] = None

    def evaluate(
        self,
        draw_number: str,
        winning_number: str,
        threshold: Optional[float] = None,
    ) -> ScoreEvaluation:
        """Evaluate the similarity and whether it passes the threshold (if any).
        This requires both a draw number and a winning number.
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
        if not replace and algorithm.key in self._algorithms:
            raise ValueError(f"Algorithm '{algorithm.key}' is already registered")
        self._algorithms[algorithm.key] = algorithm

    def get(self, key: str) -> ScoringAlgorithm:
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
        algorithm = self.get(key)
        return algorithm.evaluate(draw_number, winning_number, threshold)

    def clone(self) -> "AlgorithmRegistry":
        clone = AlgorithmRegistry()
        clone._algorithms = dict(self._algorithms)
        return clone

    def available_algorithms(self) -> Dict[str, ScoringAlgorithm]:
        return dict(self._algorithms)


def _hamming_similarity(draw_number: str, winning_number: str) -> float:
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