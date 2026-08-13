"""Dependency-light regression for P1 merge/ranking/reference semantics."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.workers.dsp_worker.temporal_analysis import detect_temporal_regions

BANDS = {"sub_bass": -4., "bass": 0., "low_mid": 1., "mid": 0., "upper_mid": -1., "presence": -2., "air": -5.}


def point(i: int, *, correlation=.75, mono_loss=-.3, side=12., low_mid=1.) -> dict:
    return {"index": i, "start_sec": i*1.5, "end_sec": i*1.5+6, "centre_sec": i*1.5+3,
            "loudness_lufs": -12., "crest_factor_db": 10., "dynamics_spread_db": 5.,
            "transient_density_hz": 2., "spectral_centroid_hz": 2200., "spectral_rolloff_hz": 6200.,
            "spectral_flatness": .05, "spectral_bandwidth_hz": 1800.,
            "stereo_width": .55, "side_energy_pct": side,
            "phase_correlation": correlation, "mono_fold_down_loss_db": mono_loss,
            "bass_side_energy_pct": 8., "band_balance_db": {**BANDS, "low_mid": low_mid}}


def main() -> int:
    stable = [point(i) for i in range(14)]
    phase_target = [dict(item) for item in stable]
    for i in (5, 6, 7): phase_target[i] = point(i, correlation=-.45, mono_loss=-3.2, side=44.)
    phase = [item for item in detect_temporal_regions({"windows": phase_target}) if item["category"] == "phase"]
    tonal_target = [dict(item) for item in stable]
    for i in (8, 9, 10): tonal_target[i] = point(i, low_mid=7.)
    refs = [{"windows": [point(i, low_mid=1.+offset) for i in range(14)]} for offset in (-.2, 0, .2)]
    tonal = next(item for item in detect_temporal_regions({"windows": tonal_target}, refs) if item["category"] == "tonal")
    comparison = phase[0].get("comparison_region") if phase else None
    checks = {
        "stationary_has_no_regions": bool(detect_temporal_regions({"windows": stable}) == []),
        "overlapping_phase_windows_merge": bool(len(phase) == 1 and len(phase[0]["window_indices"]) >= 3),
        "phase_has_multiple_metrics": bool(phase and phase[0]["confirming_metric_count"] >= 2),
        "stable_comparison_is_attached": bool(phase and phase[0]["comparison_region"]),
        "stable_comparison_does_not_overlap": bool(
            phase and comparison and (
                comparison["end_sec"] <= phase[0]["start_sec"]
                or comparison["start_sec"] >= phase[0]["end_sec"]
            )
        ),
        "three_references_support_tonal_region": bool(tonal["reference_support"] == 3),
        "unanimous_reference_region_is_high_reliability": bool(tonal["reliability"] == "HIGH"),
    }
    output = {"suite": "p1-temporal-synthetic", "checks": checks, "phase_region": phase[0], "tonal_region": tonal}
    path = Path("docs/experiments/p1-temporal-synthetic-2026-08-12.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(checks.values()): raise SystemExit(f"P1 synthetic checks failed: {checks}")
    print(json.dumps(checks, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
