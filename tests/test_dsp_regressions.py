import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from services.workers.dsp_worker import analyzer
from services.workers.dsp_worker.recommendations import generate_findings
from services.workers.dsp_worker.temporal_analysis import detect_temporal_regions


RATE = 16000


def analyze_channels(path: Path, *channels):
    sf.write(path, np.column_stack(channels), RATE, subtype="FLOAT")
    return analyzer.analyze(path, include_rhythm=False)


class DspRegressionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)

    def test_silent_stereo_has_no_fold_down_measurement_or_phase_alert(self):
        silent = np.zeros(12 * RATE)
        metrics = analyze_channels(self.directory / "silent.wav", silent, silent)
        assert metrics["stereo"]["mono_fold_down_loss_db"] is None
        assert all(w["mono_fold_down_loss_db"] is None for w in metrics["temporal"]["windows"])
        regions = detect_temporal_regions(metrics["temporal"], [metrics["temporal"]])
        assert not any(r["category"] == "phase" for r in regions)
        assert not any(f["id"] == "HYP_MONO_CANCELLATION" for f in generate_findings(metrics))


    def test_polarity_changes_fold_down_but_preserves_stereo_energy(self):
        t = np.arange(7 * RATE) / RATE
        tone = 0.5 * np.sin(2 * np.pi * 440 * t)
        aligned = analyze_channels(self.directory / "aligned.wav", tone, tone)
        opposite = analyze_channels(self.directory / "opposite.wav", tone, -tone)
        assert abs(opposite["loudness"]["rms_dbfs"] - (-9.03)) < 0.02
        assert opposite["loudness"]["crest_factor_db"] == aligned["loudness"]["crest_factor_db"]
        assert opposite["tonal"]["band_energy_pct"] == aligned["tonal"]["band_energy_pct"]
        a, b = aligned["temporal"]["windows"][0], opposite["temporal"]["windows"][0]
        for key in ("band_energy_pct", "rms_dbfs", "crest_factor_db"):
            assert b[key] == a[key]
        assert b["mono_fold_down_loss_db"] < -100
        assert "HYP_MONO_CANCELLATION" in {f["id"] for f in generate_findings(opposite)}


    def test_clean_sine_above_threshold_only_reports_near_full_scale(self):
        t = np.arange(RATE) / RATE
        tone = 0.9995 * np.sin(2 * np.pi * 1000 * t)
        loud = analyzer._loudness_metrics(tone, np.stack((tone, tone)), RATE)
        assert loud["clipping_count"] == 2000
        card = next(f for f in generate_findings({"loudness": loud}) if f["id"] == "FACT_SAMPLE_CLIPPING")
        assert "0.999 FS" in card["title"]
        assert card["priority"] != "CRITICAL"


    def test_chunked_peak_matches_continuous_interpolation(self):
        signal = np.zeros(20 * RATE)
        signal[8 * RATE:12 * RATE] = np.hanning(4 * RATE)
        expected = np.max(np.abs(resample_poly(signal, 4, 1)))
        self.assertAlmostEqual(analyzer._oversampled_peak(signal, RATE), expected, places=9)


    def test_multichannel_input_is_rejected(self):
        zero = np.zeros(RATE)
        with self.assertRaisesRegex(RuntimeError, "3 channels"):
            analyze_channels(self.directory / "three.wav", zero, zero, np.ones(RATE))
