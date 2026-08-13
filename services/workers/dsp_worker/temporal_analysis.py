"""Windowed evidence and region detection for SoundDebug P1.

The module deliberately detects *where measurements change*.  It does not try
to name song sections or infer a corrective plugin setting from a stereo file.
"""

from __future__ import annotations

from collections import defaultdict
from math import log1p
from typing import Any

import numpy as np
from scipy.signal import butter, sosfilt

WINDOW_SEC = 6.0
HOP_SEC = 1.5
MIN_REGION_SCORE = 2.2
EPS = 1e-12
FREQ_BANDS = ("sub_bass", "bass", "low_mid", "mid", "upper_mid", "presence", "air")


def _finite(value: float, digits: int = 3) -> float:
    return round(float(value), digits) if np.isfinite(value) else 0.0


def _waveform_envelope(y_mono: np.ndarray, bins: int = 240) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for indexes in np.array_split(np.arange(len(y_mono)), min(bins, len(y_mono))):
        chunk = y_mono[indexes]
        result.append({
            "peak": _finite(np.max(np.abs(chunk)), 4),
            "rms": _finite(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))), 4),
        })
    return result


def extract_temporal_features(
    y_mono: np.ndarray, y_stereo: np.ndarray | None, sr: int,
) -> dict[str, Any]:
    """Build one synchronized feature vector for every overlapping window."""
    import librosa
    from .analyzer import _band_statistics, _k_weight, _loudness_from_power, _safe_corr, _to_db, _window_starts
    window_samples = max(1, int(WINDOW_SEC * sr))
    starts = _window_starts(len(y_mono), sr, WINDOW_SEC, HOP_SEC)
    weighted_source = y_stereo.T if y_stereo is not None else y_mono[:, np.newaxis]
    weighted = _k_weight(weighted_source, sr)
    cutoff = min(150.0, sr * 0.45)
    lowpass = butter(4, cutoff, btype="lowpass", fs=sr, output="sos")
    windows: list[dict[str, Any]] = []

    for index, start in enumerate(starts):
        end = min(len(y_mono), start + window_samples)
        mono = y_mono[start:end]
        channels = y_stereo[:, start:end] if y_stereo is not None else None
        weighted_chunk = weighted[start:end]
        loudness = _loudness_from_power(float(np.sum(np.mean(weighted_chunk * weighted_chunk, axis=0))))

        n_fft = min(4096, max(256, 2 ** int(np.floor(np.log2(max(256, len(mono)))))))
        spectrum = np.abs(librosa.stft(mono, n_fft=n_fft, hop_length=max(64, n_fft // 4))) ** 2
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
        shares, balance = _band_statistics(np.mean(spectrum, axis=1), freqs)
        magnitude = np.sqrt(spectrum)

        rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))
        peak = float(np.max(np.abs(mono)))
        frame_rms = librosa.feature.rms(y=mono, frame_length=min(2048, len(mono)), hop_length=512)[0]
        active_db = 20 * np.log10(frame_rms[frame_rms > 1e-7] + EPS)
        dynamics_spread = float(np.percentile(active_db, 90) - np.percentile(active_db, 10)) if len(active_db) >= 4 else 0.0
        onset_env = librosa.onset.onset_strength(y=mono, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)

        if channels is None:
            width, correlation, mono_loss, side_share, bass_side = 0.0, 1.0, 0.0, 0.0, 0.0
        else:
            left, right = channels
            mid, side = (left + right) / 2.0, (left - right) / 2.0
            mid_power = float(np.mean(mid * mid))
            side_power = float(np.mean(side * side))
            stereo_rms = float(np.sqrt(np.mean((left * left + right * right) / 2.0)))
            width = np.sqrt(side_power) / (np.sqrt(mid_power) + EPS)
            correlation = _safe_corr(left, right)
            mono_loss = _to_db(np.sqrt(mid_power) / (stereo_rms + EPS))
            side_share = 100.0 * side_power / (mid_power + side_power + EPS)
            low_mid = sosfilt(lowpass, mid)
            low_side = sosfilt(lowpass, side)
            bass_side = 100.0 * float(np.sum(low_side * low_side)) / (
                float(np.sum(low_mid * low_mid) + np.sum(low_side * low_side)) + EPS
            )

        windows.append({
            "index": index,
            "start_sec": round(start / sr, 3),
            "end_sec": round(end / sr, 3),
            "centre_sec": round((start + end) / 2 / sr, 3),
            "loudness_lufs": _finite(loudness, 2),
            "rms_dbfs": _finite(_to_db(rms), 2),
            "crest_factor_db": _finite(_to_db(peak) - _to_db(rms), 2),
            "dynamics_spread_db": _finite(dynamics_spread, 2),
            "transient_density_hz": _finite(len(onsets) / max((end - start) / sr, EPS), 3),
            "spectral_centroid_hz": _finite(np.median(librosa.feature.spectral_centroid(S=magnitude, sr=sr)), 1),
            "spectral_rolloff_hz": _finite(np.median(librosa.feature.spectral_rolloff(S=magnitude, sr=sr)), 1),
            "spectral_flatness": _finite(np.median(librosa.feature.spectral_flatness(S=magnitude)), 5),
            "spectral_bandwidth_hz": _finite(np.median(librosa.feature.spectral_bandwidth(S=magnitude, sr=sr)), 1),
            "band_energy_pct": {key: _finite(value, 3) for key, value in shares.items()},
            "band_balance_db": {key: _finite(value, 2) for key, value in balance.items()},
            "mid_energy_pct": _finite(100.0 - side_share, 2),
            "side_energy_pct": _finite(side_share, 2),
            "stereo_width": _finite(width, 4),
            "phase_correlation": _finite(correlation, 4),
            "mono_fold_down_loss_db": _finite(mono_loss, 2),
            "bass_side_energy_pct": _finite(bass_side, 2),
        })

    return {
        "window_sec": WINDOW_SEC,
        "hop_sec": HOP_SEC,
        "windows": windows,
        "waveform_envelope": _waveform_envelope(y_mono),
        "method": "overlapping-window-feature-vector-p1",
    }


SCALAR_FEATURES: dict[str, tuple[str, float, str]] = {
    "loudness_lufs": ("loudness", 3.0, "LU"),
    "crest_factor_db": ("dynamics", 2.5, "dB"),
    "dynamics_spread_db": ("dynamics", 2.5, "dB"),
    "transient_density_hz": ("dynamics", 0.8, "events/s"),
    "spectral_centroid_hz": ("spectral", 700.0, "Hz"),
    "spectral_rolloff_hz": ("spectral", 1200.0, "Hz"),
    "spectral_bandwidth_hz": ("spectral", 700.0, "Hz"),
    "spectral_flatness": ("spectral", 0.035, "ratio"),
    "stereo_width": ("stereo", 0.22, "ratio"),
    "side_energy_pct": ("stereo", 12.0, "%"),
    "phase_correlation": ("phase", 0.25, "correlation"),
    "mono_fold_down_loss_db": ("phase", 1.0, "dB"),
    "bass_side_energy_pct": ("stereo", 12.0, "%"),
}


def _value(window: dict[str, Any], feature: str) -> float:
    if feature.startswith("band:"):
        return float(window["band_balance_db"][feature.split(":", 1)[1]])
    return float(window[feature])


def _robust(values: list[float]) -> tuple[float, float]:
    centre = float(np.median(values))
    mad = float(np.median(np.abs(np.asarray(values) - centre)))
    return centre, max(1.4826 * mad, EPS)


def _reference_vote(
    target_value: float, feature: str, references: list[dict[str, Any]], threshold: float,
) -> tuple[int, int, float | None, str]:
    distributions: list[tuple[float, float]] = []
    for reference in references:
        windows = reference.get("windows", [])
        values = [_value(window, feature) for window in windows]
        if values:
            centre, scale = _robust(values)
            distributions.append((centre, scale))
    if not distributions:
        return 0, 0, None, "NONE"
    medians = [item[0] for item in distributions]
    ref_centre = float(np.median(medians))
    direction = np.sign(target_value - ref_centre)
    support = int(sum(
        bool(
            abs(target_value - centre) >= max(threshold, 2.5 * scale)
            and np.sign(target_value - centre) == direction
        )
        for centre, scale in distributions
    ))
    count = len(medians)
    reliability = "HIGH" if count >= 3 and support == count else "MEDIUM" if support >= 2 and support / count >= 2 / 3 else "LOW"
    return support, count, target_value - ref_centre, reliability


def _signals_for_window(
    windows: list[dict[str, Any]], index: int, references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target = windows[index]
    neighbours = [window for pos, window in enumerate(windows) if 1 <= abs(pos - index) <= 3]
    if len(neighbours) < 2:
        neighbours = [window for pos, window in enumerate(windows) if pos != index]
    definitions = dict(SCALAR_FEATURES)
    definitions.update({f"band:{band}": ("tonal", 2.5, "dB") for band in FREQ_BANDS})
    result: list[dict[str, Any]] = []
    for feature, (category, minimum, unit) in definitions.items():
        value = _value(target, feature)
        local_values = [_value(window, feature) for window in neighbours]
        if len(local_values) < 2:
            continue
        local_centre, local_scale = _robust(local_values)
        delta = value - local_centre
        adaptive = max(minimum, 2.75 * local_scale)
        local_score = abs(delta) / adaptive
        support, count, ref_delta, reliability = _reference_vote(value, feature, references, minimum)
        reference_score = abs(ref_delta) / minimum if ref_delta is not None and support >= 2 else 0.0

        absolute_risk = (
            feature == "phase_correlation" and value < 0.0
            or feature == "mono_fold_down_loss_db" and value < -2.0
            or feature == "bass_side_energy_pct" and value > 30.0
        )
        if max(local_score, reference_score) < 1.0 and not absolute_risk:
            continue
        result.append({
            "feature": feature,
            "category": category,
            "value": round(value, 3),
            "unit": unit,
            "local_baseline": round(local_centre, 3),
            "local_delta": round(delta, 3),
            "magnitude": round(max(local_score, reference_score, 1.0 if absolute_risk else 0.0), 3),
            "reference_delta": round(ref_delta, 3) if ref_delta is not None else None,
            "reference_support": support,
            "reference_count": count,
            "reference_reliability": reliability,
        })
    return result


def _merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["category"]].append(candidate)
    merged: list[dict[str, Any]] = []
    for category, items in groups.items():
        items.sort(key=lambda item: item["start_sec"])
        current: list[dict[str, Any]] = []
        for item in items:
            if current and item["start_sec"] > current[-1]["end_sec"] + HOP_SEC * 1.1:
                merged.append(_finish_region(category, current))
                current = []
            current.append(item)
        if current:
            merged.append(_finish_region(category, current))
    return merged


def _finish_region(category: str, windows: list[dict[str, Any]]) -> dict[str, Any]:
    signal_map: dict[str, dict[str, Any]] = {}
    for window in windows:
        for signal in window["signals"]:
            previous = signal_map.get(signal["feature"])
            if previous is None or signal["magnitude"] > previous["magnitude"]:
                signal_map[signal["feature"]] = signal
    signals = sorted(signal_map.values(), key=lambda item: item["magnitude"], reverse=True)
    start = min(item["start_sec"] for item in windows)
    end = max(item["end_sec"] for item in windows)
    magnitude = float(np.mean([item["magnitude"] for item in signals[:3]]))
    metrics_count = len(signals)
    strongest = signals[0] if signals else {}
    ref_support = int(strongest.get("reference_support", 0))
    ref_count = int(strongest.get("reference_count", 0))
    reliability = "HIGH" if ref_count >= 3 and ref_support == ref_count else "MEDIUM" if metrics_count >= 2 or ref_support >= 2 else "LOW"
    duration = end - start
    reference_component = 1.0 if reliability == "HIGH" else 0.5 if reliability == "MEDIUM" else 0.0
    score = magnitude * 2.0 + min(metrics_count, 4) * 0.6 + log1p(duration) * 0.35 + reference_component
    return {
        "category": category,
        "start_sec": round(start, 3),
        "end_sec": round(end, 3),
        "duration_sec": round(duration, 3),
        "score": round(score, 3),
        "reliability": reliability,
        "confirming_metric_count": metrics_count,
        "reference_support": ref_support,
        "reference_count": ref_count,
        "reference_support_ratio": round(ref_support / ref_count, 3) if ref_count else None,
        "ranking": {
            "magnitude": round(magnitude, 3),
            "duration_sec": round(duration, 3),
            "confirming_metric_count": metrics_count,
            "reference_stability": reliability,
        },
        "evidence": signals[:6],
        "window_indices": sorted({item["index"] for item in windows}),
    }


def detect_temporal_regions(
    temporal: dict[str, Any], reference_temporals: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Detect, merge and rank meaningful deviations in a target timeline."""
    windows = temporal.get("windows", [])
    references = reference_temporals or []
    candidates: list[dict[str, Any]] = []
    for index, window in enumerate(windows):
        signals = _signals_for_window(windows, index, references)
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            by_category[signal["category"]].append(signal)
        for category, category_signals in by_category.items():
            candidates.append({
                "index": index,
                "category": category,
                "start_sec": window["start_sec"],
                "end_sec": window["end_sec"],
                "signals": category_signals,
            })

    regions = [item for item in _merge_candidates(candidates) if item["score"] >= MIN_REGION_SCORE]
    anomalous_windows = {index for region in regions for index in region["window_indices"]}
    stable_windows = [window for window in windows if window["index"] not in anomalous_windows]
    for position, region in enumerate(sorted(regions, key=lambda item: (-item["score"], item["start_sec"])), 1):
        region["id"] = f"region-{position:03d}"
        region["finding_id"] = f"TEMPORAL_{region['category'].upper()}_{position:03d}"
        non_overlapping_stable = [
            window for window in stable_windows
            if window["end_sec"] <= region["start_sec"] or window["start_sec"] >= region["end_sec"]
        ]
        if non_overlapping_stable:
            centre = (region["start_sec"] + region["end_sec"]) / 2
            stable = min(non_overlapping_stable, key=lambda item: abs(item["centre_sec"] - centre))
            region["comparison_region"] = {
                "start_sec": stable["start_sec"], "end_sec": stable["end_sec"],
                "reason": "nearest window without a ranked anomaly",
            }
        else:
            region["comparison_region"] = None
    # Every public region must have a corresponding diagnostic card.  Keeping
    # the public set bounded prevents a marker from pointing to a card that was
    # intentionally omitted from the report.
    return sorted(regions, key=lambda item: (-item["score"], item["start_sec"]))[:12]
