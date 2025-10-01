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
        score = float(self.scorer(draw_number, winning_number))
        passed = None if threshold is None else score <= threshold
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


def _hamming_distance(draw_number: str, winning_number: str) -> float:
    try:
        left: bytes = draw_number.encode("ascii")
        right: bytes = winning_number.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "draw and winning numbers must contain only ASCII characters"
        ) from exc
    if not left and not right:
        return 0.0
    max_len = max(len(left), len(right))
    padded_left = left.ljust(max_len, b"\x00")
    padded_right = right.ljust(max_len, b"\x00")
    xor_result = int.from_bytes(padded_left, "big") ^ int.from_bytes(
        padded_right, "big"
    )
    return float(xor_result.bit_count())


DEFAULT_SCORING_REGISTRY = AlgorithmRegistry()
DEFAULT_SCORING_REGISTRY.register(
    ScoringAlgorithm(
        key="hamming",
        scorer=_hamming_distance,
        description="Character-wise Hamming distance (with zero padding for unequal lengths)."
        "The lower the score, the more similar the two strings are.",
    )
)


__all__ = [
    "AlgorithmRegistry",
    "DEFAULT_SCORING_REGISTRY",
    "ScoreEvaluation",
    "ScoringAlgorithm",
]
