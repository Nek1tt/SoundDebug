import json
import unittest
from pathlib import Path

from services.workers.reference_worker.curve_matcher import compare_to_genre, compare_to_references


def metrics(lufs: float, width: float, offset: float = 0.0) -> dict:
    bands = {
        "sub_bass": -20.0 + offset,
        "bass": -18.0 + offset,
        "low_mid": -22.0 + offset,
        "mid": -21.0 + offset,
        "upper_mid": -23.0 + offset,
        "presence": -25.0 + offset,
        "air": -28.0 + offset,
    }
    return {
        "loudness": {"lufs": lufs},
        "tonal": {"band_energy_db": bands},
        "stereo": {"stereo_width": width},
    }


class ReferenceMatcherTests(unittest.TestCase):
    def test_reference_median_and_delta(self):
        result = compare_to_references(
            metrics(-10.0, 0.8, 3.0),
            [metrics(-14.0, 0.5), metrics(-12.0, 0.7, 2.0)],
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "references")
        self.assertEqual(result["reference_count"], 2)
        self.assertEqual(result["lufs_delta"], 3.0)
        self.assertAlmostEqual(result["stereo_width_delta"], 0.2)
        self.assertEqual(result["tonal_delta_db"]["bass"], 2.0)

    def test_all_genre_profiles_are_valid(self):
        root = Path(__file__).parents[1] / "data" / "genre-curves"
        for genre in ("lo-fi", "modern-pop", "hip-hop", "techno", "electronic"):
            profile = json.loads((root / f"{genre}.json").read_text(encoding="utf-8"))
            self.assertEqual(len(profile["relative_band_db"]), 7)
            result = compare_to_genre(metrics(-12.0, 0.5), genre, root)
            self.assertEqual(result["source"], "genre-profile")


if __name__ == "__main__":
    unittest.main()
