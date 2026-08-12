"""Small deterministic experiment suite for the v2 feature semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.workers.dsp_worker.analyzer import _loudness_metrics, _stereo_metrics, _tonal_metrics
from services.workers.dsp_worker.recommendations import generate_recommendations
from services.workers.reference_worker.curve_matcher import compare_to_references


def package(tonal: dict, lufs: float = -14.0) -> dict:
    return {"tonal": tonal, "loudness": {"integrated_lufs": lufs}, "stereo": {"stereo_width": 0.5}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/experiments/dsp-v2-synthetic-2026-08-11.json"))
    args = parser.parse_args()

    sr = 22050
    t = np.arange(sr * 9) / sr
    base = (
        0.12 * np.sin(2 * np.pi * 90 * t)
        + 0.09 * np.sin(2 * np.pi * 440 * t)
        + 0.04 * np.sin(2 * np.pi * 3500 * t)
    ).astype(np.float32)
    target = (base + 0.14 * np.sin(2 * np.pi * 48 * t)).astype(np.float32)

    tonal_base = _tonal_metrics(base, sr)
    tonal_quiet = _tonal_metrics(base * 0.1, sr)
    tonal_target = _tonal_metrics(target, sr)
    max_gain_delta = max(
        abs(tonal_base["band_energy_pct"][band] - tonal_quiet["band_energy_pct"][band])
        for band in tonal_base["band_energy_pct"]
    )
    sub_bass_increase = tonal_target["band_energy_pct"]["sub_bass"] - tonal_base["band_energy_pct"]["sub_bass"]

    reference = compare_to_references(
        package(tonal_target, -11.0),
        [package(tonal_base, -14.0), package(_tonal_metrics(base + 0.005 * np.sin(2 * np.pi * 8000 * t), sr), -13.5)],
    )

    left = base.copy()
    right = base.copy()
    right[sr * 3 : sr * 5] *= -1
    stereo = np.vstack((left, right))
    spatial = _stereo_metrics(np.mean(stereo, axis=0), stereo, sr)

    unclipped = _loudness_metrics(base, None, sr)
    clipped_audio = base.copy()
    clipped_audio[sr : sr + 200] = 1.0
    clipped = _loudness_metrics(clipped_audio, None, sr)

    diagnostic_metrics = {"loudness": unclipped, "stereo": spatial}
    diagnostics = generate_recommendations(diagnostic_metrics, "techno", reference)
    tonal_advice = " ".join(
        " ".join(item["daw_check_steps"]) + " " + item["do_not_automate"]
        for item in diagnostics if item["category"] == "tonal_balance"
    )

    result = {
        "experiment": "SoundDebug P0 trustworthy diagnostic invariants",
        "date": "2026-08-12",
        "sample_rate": sr,
        "results": {
            "band_share_sum_pct": round(sum(tonal_base["band_energy_pct"].values()), 4),
            "max_band_share_change_after_minus_20_db_gain_pct_points": round(max_gain_delta, 6),
            "sub_bass_share_increase_after_48_hz_component_pct_points": round(sub_bass_increase, 3),
            "reference_sub_bass_delta_db": reference["tonal_shape_difference"].get("sub_bass", {}).get("difference_db") if reference else None,
            "minimum_local_phase_correlation": spatial["minimum_phase_correlation"],
            "phase_risk_segment_count": len(spatial["phase_risk_segments"]),
            "clean_clipping_samples": unclipped["clipping_count"],
            "injected_clipping_samples": clipped["clipping_count"],
            "tonal_advice_contains_plugin_setting": "q=" in tonal_advice.lower() or "eq -" in tonal_advice.lower(),
        },
        "checks": {
            "shares_sum_to_100": abs(sum(tonal_base["band_energy_pct"].values()) - 100.0) < 0.02,
            "gain_invariant": max_gain_delta < 0.01,
            "sub_bass_change_detected": sub_bass_increase > 10.0,
            "anti_phase_localised": spatial["minimum_phase_correlation"] < 0 and bool(spatial["phase_risk_segments"]),
            "clipping_injection_detected": clipped["clipping_count"] > unclipped["clipping_count"],
            "no_direct_eq_command": "q=" not in tonal_advice.lower() and "eq -" not in tonal_advice.lower(),
        },
    }
    result["passed"] = all(result["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
