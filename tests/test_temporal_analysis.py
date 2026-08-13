from __future__ import annotations

import unittest

from services.workers.dsp_worker.temporal_analysis import detect_temporal_regions


BANDS = {"sub_bass": -4.0, "bass": 0.0, "low_mid": 1.0, "mid": 0.0, "upper_mid": -1.0, "presence": -2.0, "air": -5.0}


def window(index: int, *, correlation: float = .75, mono_loss: float = -.3, side: float = 12.0, low_mid: float = 1.0) -> dict:
    return {
        "index": index, "start_sec": index * 1.5, "end_sec": index * 1.5 + 6,
        "centre_sec": index * 1.5 + 3, "loudness_lufs": -12.0,
        "crest_factor_db": 10.0, "dynamics_spread_db": 5.0, "transient_density_hz": 2.0,
        "spectral_centroid_hz": 2200.0, "spectral_rolloff_hz": 6200.0, "spectral_flatness": .05,
        "spectral_bandwidth_hz": 1800.0,
        "stereo_width": .55, "side_energy_pct": side, "phase_correlation": correlation,
        "mono_fold_down_loss_db": mono_loss, "bass_side_energy_pct": 8.0,
        "band_balance_db": {**BANDS, "low_mid": low_mid},
    }


class TemporalRegionTests(unittest.TestCase):
    def test_overlapping_phase_windows_merge_into_one_region(self):
        windows = [window(i) for i in range(12)]
        for i in (5, 6, 7):
            windows[i] = window(i, correlation=-.45, mono_loss=-3.2, side=44.0)
        regions = detect_temporal_regions({"windows": windows})
        phase = [item for item in regions if item["category"] == "phase"]
        self.assertEqual(len(phase), 1)
        self.assertGreaterEqual(phase[0]["confirming_metric_count"], 2)
        self.assertIsNotNone(phase[0]["comparison_region"])
        stable = phase[0]["comparison_region"]
        self.assertTrue(
            stable["end_sec"] <= phase[0]["start_sec"]
            or stable["start_sec"] >= phase[0]["end_sec"]
        )
        self.assertIn("magnitude", phase[0]["ranking"])
        self.assertIn("duration_sec", phase[0]["ranking"])

    def test_stationary_windows_do_not_create_regions(self):
        self.assertEqual(detect_temporal_regions({"windows": [window(i) for i in range(12)]}), [])

    def test_reference_support_increases_reliability(self):
        target = [window(i) for i in range(12)]
        for i in (5, 6, 7):
            target[i] = window(i, low_mid=7.0)
        references = [{"windows": [window(i, low_mid=1.0 + offset) for i in range(12)]} for offset in (-.2, 0, .2)]
        tonal = next(item for item in detect_temporal_regions({"windows": target}, references) if item["category"] == "tonal")
        self.assertEqual(tonal["reference_support"], 3)
        self.assertEqual(tonal["reliability"], "HIGH")

    def test_wide_reference_distribution_does_not_create_false_consensus(self):
        target = [window(i) for i in range(12)]
        for i in (5, 6, 7):
            target[i] = window(i, low_mid=7.0)
        variable = []
        for offset in (-1.0, 0.0, 1.0):
            ref_windows = [window(i, low_mid=(-4.0 if i % 2 else 6.0) + offset) for i in range(12)]
            variable.append({"windows": ref_windows})
        tonal = next(item for item in detect_temporal_regions({"windows": target}, variable) if item["category"] == "tonal")
        self.assertLess(tonal["reference_support"], 3)
        self.assertNotEqual(tonal["reliability"], "HIGH")


if __name__ == "__main__":
    unittest.main()
