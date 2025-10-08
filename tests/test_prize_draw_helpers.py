from __future__ import annotations

import unittest

from nictbw.prize_draw import (
    AlgorithmRegistry,
    DEFAULT_SCORING_REGISTRY,
    ScoreEvaluation,
    ScoringAlgorithm,
    derive_draw_number,
)


class DrawNumberGenerationTests(unittest.TestCase):
    def test_default_generator_is_stable(self) -> None:
        origin = "TxId:0001"
        origin_lower = origin.lower()
        first = derive_draw_number(origin)
        second = derive_draw_number(f"  {origin}  ")
        self.assertEqual(first, origin_lower)
        self.assertEqual(second, origin_lower)

    def test_empty_origin_raises(self) -> None:
        with self.assertRaises(ValueError):
            derive_draw_number("   ")

    def test_non_string_origin_raises(self) -> None:
        with self.assertRaises(TypeError):
            derive_draw_number(123)  # type: ignore[arg-type]


class ScoringRegistryTests(unittest.TestCase):
    def test_default_registry_contains_expected_algorithms(self) -> None:
        available = DEFAULT_SCORING_REGISTRY.available_algorithms()
        self.assertIn("hamming", available)

    def test_hamming_similarity_with_threshold(self) -> None:
        result = DEFAULT_SCORING_REGISTRY.evaluate("hamming", "abcd", "abce", threshold=0.5)
        self.assertIsInstance(result, ScoreEvaluation)
        self.assertEqual(result.algorithm_key, "hamming")
        self.assertAlmostEqual(result.score, 0.96875)
        self.assertTrue(result.passed)

    def test_custom_registry_registration(self) -> None:
        registry = AlgorithmRegistry()
        with self.assertRaises(KeyError):
            registry.get("missing")
        registry.register(DEFAULT_SCORING_REGISTRY.get("hamming"))
        with self.assertRaises(ValueError):
            registry.register(DEFAULT_SCORING_REGISTRY.get("hamming"))
        evaluation = registry.evaluate("hamming", "A", "B", threshold=0.5)
        # ASCII A (0x41) vs B (0x42) differ by two bits leading to 0.75 similarity.
        self.assertAlmostEqual(evaluation.score, 0.75)
        self.assertTrue(evaluation.passed)

if __name__ == "__main__":
    unittest.main()

