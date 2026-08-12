import json
import unittest
from pathlib import Path

from services.workers.reference_worker.curve_matcher import compare_to_genre, compare_to_references


BASE_BANDS = {
    "sub_bass": -3.0, "bass": 1.0, "low_mid": 2.0, "mid": 0.0,
    "upper_mid": -1.0, "presence": -2.0, "air": -5.0,
}


def metrics(lufs: float, width: float, *, low_mid: float = 2.0, plr: float = 9.0) -> dict:
    bands = {**BASE_BANDS, "low_mid": low_mid}
    return {
        "loudness": {
            "integrated_lufs": lufs, "plr_lu": plr,
            "short_term_loudness_spread_lu": 4.0, "crest_factor_db": 10.0,
        },
        "tonal": {"band_balance_db": bands},
        "stereo": {
            "stereo_width": width, "phase_correlation": 0.7,
            "mono_fold_down_loss_db": -0.5, "bass_side_energy_pct": 8.0,
        },
    }


class ReferenceMatcherTests(unittest.TestCase):
    def test_domains_are_separate_and_tonal_shape_is_level_independent(self):
        result = compare_to_references(
            metrics(-10.0, 0.8, low_mid=6.0, plr=6.0),
            [metrics(-14.0, 0.5, low_mid=1.0), metrics(-12.0, 0.7, low_mid=2.0)],
        )
        self.assertEqual(result["source"], "references")
        self.assertEqual(result["loudness_difference"]["difference"], 3.0)
        self.assertAlmostEqual(result["stereo_difference"]["width"]["difference"], 0.2)
        self.assertEqual(result["dynamics_difference"]["plr"]["difference"], -3.0)
        self.assertEqual(result["tonal_shape_difference"]["low_mid"]["difference_db"], 4.5)
        self.assertTrue(result["loudness_matching"]["applied_to_tonal_shape"])
        self.assertNotIn("similarity_percent", result)

    def test_one_of_three_does_not_look_like_consensus(self):
        target = metrics(-12.0, 0.5, low_mid=6.0)
        result = compare_to_references(target, [
            metrics(-12.0, 0.5, low_mid=5.5),
            metrics(-12.0, 0.5, low_mid=5.0),
            metrics(-12.0, 0.5, low_mid=0.0),
        ])
        finding = result["tonal_shape_difference"]["low_mid"]
        self.assertEqual(finding["support_count"], 1)
        self.assertEqual(finding["reliability"], "LOW")

    def test_three_of_three_can_be_high_reliability(self):
        target = metrics(-12.0, 0.5, low_mid=7.0)
        result = compare_to_references(target, [
            metrics(-12.0, 0.5, low_mid=2.0),
            metrics(-12.0, 0.5, low_mid=2.2),
            metrics(-12.0, 0.5, low_mid=1.8),
        ])
        finding = result["tonal_shape_difference"]["low_mid"]
        self.assertEqual(finding["support_count"], 3)
        self.assertEqual(finding["reliability"], "HIGH")

    def test_all_genre_profiles_are_context_only(self):
        root = Path(__file__).parents[1] / "data" / "genre-curves"
        for genre in ("lo-fi", "modern-pop", "hip-hop", "techno", "electronic"):
            profile = json.loads((root / f"{genre}.json").read_text(encoding="utf-8"))
            self.assertEqual(len(profile["relative_band_db"]), 7)
            result = compare_to_genre(metrics(-12.0, 0.5), genre, root)
            self.assertEqual(result["source"], "genre-profile")
            self.assertIn("контекст", result["note"].lower())


if __name__ == "__main__":
    unittest.main()
