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
        self.assertIn("sha256_hex_proximity", available)

    def test_sha256_hex_similarity_with_threshold(self) -> None:
        result = DEFAULT_SCORING_REGISTRY.evaluate(
            "sha256_hex_proximity", "abcd", "abce", threshold=0.8
        )
        self.assertIsInstance(result, ScoreEvaluation)
        self.assertEqual(result.algorithm_key, "sha256_hex_proximity")
        self.assertAlmostEqual(result.score, 0.8769994616139306)
        self.assertEqual(result.draw_top_digits, "6188938426")
        self.assertEqual(result.winning_top_digits, "6011386400")
        self.assertTrue(result.passed)

    def test_custom_registry_registration(self) -> None:
        registry = AlgorithmRegistry()
        with self.assertRaises(KeyError):
            registry.get("missing")
        registry.register(DEFAULT_SCORING_REGISTRY.get("sha256_hex_proximity"))
        with self.assertRaises(ValueError):
            registry.register(DEFAULT_SCORING_REGISTRY.get("sha256_hex_proximity"))
        evaluation = registry.evaluate("sha256_hex_proximity", "A", "B", threshold=0.05)
        # SHA-256 hashed values for A and B yield a low similarity via the hex scorer.
        self.assertAlmostEqual(evaluation.score, 0.09205801963150056)
        self.assertEqual(evaluation.draw_top_digits, "3872030720")
        self.assertEqual(evaluation.winning_top_digits, "1010891671")
        self.assertTrue(evaluation.passed)

if __name__ == "__main__":
    unittest.main()
