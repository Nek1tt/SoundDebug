from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from services.workers.dsp_worker.analyzer import _stereo_metrics, _tonal_metrics, analyze
from services.workers.dsp_worker.temporal_analysis import detect_temporal_regions


class DspV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sr = 22050
        seconds = 8
        t = np.arange(cls.sr * seconds) / cls.sr
        pulse = (np.sin(2 * np.pi * 2 * t) > 0.85).astype(float)
        mono = 0.18 * np.sin(2 * np.pi * 110 * t) + 0.08 * np.sin(2 * np.pi * 880 * t) + 0.04 * pulse
        stereo = np.column_stack((mono, 0.96 * mono + 0.01 * np.sin(2 * np.pi * 330 * t)))
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "mix.wav"
        sf.write(cls.path, stereo, cls.sr, subtype="FLOAT")
        cls.result = analyze(cls.path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_v2_contract(self):
        self.assertEqual(self.result["meta"]["analysis_version"], "dsp-v3-temporal")
        self.assertEqual(self.result["tonal"]["representation"], "power-share-and-centred-log-ratio-v2")
        self.assertIn("loudness_timeline", self.result["loudness"])
        self.assertIn("short_term_loudness_spread_lu", self.result["loudness"])
        self.assertNotIn("loudness_range_lu", self.result["loudness"])
        self.assertIn("mono_fold_down_loss_db", self.result["stereo"])
        self.assertIn("key_confidence", self.result["rhythm"])
        self.assertIn("temporal", self.result)
        self.assertGreater(len(self.result["temporal"]["windows"]), 1)
        first = self.result["temporal"]["windows"][0]
        for key in ("loudness_lufs", "crest_factor_db", "transient_density_hz", "band_balance_db", "mid_energy_pct", "side_energy_pct", "stereo_width", "phase_correlation", "mono_fold_down_loss_db"):
            self.assertIn(key, first)

    def test_band_shares_are_percentages(self):
        shares = self.result["tonal"]["band_energy_pct"]
        self.assertEqual(set(shares), {"sub_bass", "bass", "low_mid", "mid", "upper_mid", "presence", "air"})
        self.assertAlmostEqual(sum(shares.values()), 100.0, places=1)
        self.assertTrue(all(0 <= value <= 100 for value in shares.values()))

    def test_tonal_profile_is_gain_invariant(self):
        y, sr = sf.read(self.path, dtype="float32")
        mono = np.mean(y, axis=1)
        first = _tonal_metrics(mono, sr)["band_energy_pct"]
        second = _tonal_metrics(mono * 0.2, sr)["band_energy_pct"]
        for band in first:
            self.assertAlmostEqual(first[band], second[band], places=2)

    def test_antiphase_is_localised(self):
        t = np.arange(self.sr * 7) / self.sr
        left = 0.2 * np.sin(2 * np.pi * 220 * t)
        right = left.copy()
        right[self.sr * 3 : self.sr * 5] *= -1
        stereo = np.vstack((left, right))
        result = _stereo_metrics(np.mean(stereo, axis=0), stereo, self.sr)
        self.assertLess(result["minimum_phase_correlation"], 0)
        self.assertTrue(result["phase_risk_segments"])

    def test_identical_stereo_channels_are_labelled_dual_mono(self):
        t = np.arange(self.sr * 4) / self.sr
        mono = 0.2 * np.sin(2 * np.pi * 220 * t)
        result = _stereo_metrics(mono, np.vstack((mono, mono)), self.sr)
        self.assertTrue(result["is_mono"])
        self.assertEqual(result["channel_layout"], "dual-mono")

    def test_real_window_pipeline_localises_phase_region(self):
        seconds = 20
        t = np.arange(self.sr * seconds) / self.sr
        left = 0.16 * np.sin(2 * np.pi * 220 * t) + 0.04 * np.sin(2 * np.pi * 880 * t)
        right = left.copy()
        right[self.sr * 8 : self.sr * 12] *= -0.85
        path = Path(self.temp.name) / "local-phase.wav"
        sf.write(path, np.column_stack((left, right)), self.sr, subtype="FLOAT")
        metrics = analyze(path, include_rhythm=False)
        regions = detect_temporal_regions(metrics["temporal"])
        phase = [item for item in regions if item["category"] == "phase"]
        self.assertTrue(phase)
        self.assertLessEqual(phase[0]["start_sec"], 12.0)
        self.assertGreaterEqual(phase[0]["end_sec"], 8.0)
        self.assertGreaterEqual(phase[0]["confirming_metric_count"], 2)


if __name__ == "__main__":
    unittest.main()
