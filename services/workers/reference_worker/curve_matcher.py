"""Reference-conditioned comparisons for finished mixes.

P0 treats every reference track as one independent vote.  Segments inside a
track describe variation over time, but never inflate the number of references.
All level-dependent and level-independent dimensions are kept separate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

MIN_TONAL_DELTA_DB = 3.0
MIN_LOUDNESS_DELTA_LU = 2.0
MIN_STEREO_WIDTH_DELTA = 0.15
MIN_DYNAMICS_DELTA = 1.5


def _bands(item: dict[str, Any]) -> dict[str, float]:
    tonal = item.get("tonal", {})
    return tonal.get("band_balance_db") or tonal.get("band_energy_db") or {}


def _number(item: dict[str, Any], *path: str) -> float | None:
    current: Any = item
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    try:
        value = float(current)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _median_mad(values: list[float]) -> tuple[float, float]:
    centre = float(np.median(values))
    mad = float(np.median(np.abs(np.asarray(values, dtype=float) - centre)))
    return centre, mad


def _reliability(reference_count: int, support_count: int, dispersion: float, threshold: float) -> tuple[str, str]:
    if reference_count < 2:
        return "LOW", "Доступен только один референс: устойчивость между треками проверить нельзя."
    unanimous = support_count == reference_count
    low_dispersion = dispersion <= threshold * 0.5
    if reference_count >= 3 and unanimous and low_dispersion:
        return "HIGH", f"Направление повторяется во всех {reference_count} референсах, разброс небольшой."
    if support_count >= 2 and support_count / reference_count >= 2 / 3:
        return "MEDIUM", f"Направление поддерживают {support_count} из {reference_count} референсов."
    return "LOW", f"Направление поддерживают только {support_count} из {reference_count} референсов."


def _dimension(
    target_value: float | None,
    references: list[dict[str, Any]],
    getter: Callable[[dict[str, Any]], float | None],
    threshold: float,
    unit: str,
) -> dict[str, Any] | None:
    if target_value is None:
        return None
    values = [value for item in references if (value := getter(item)) is not None]
    if not values:
        return None
    centre, mad = _median_mad(values)
    deltas = [target_value - value for value in values]
    median_delta = target_value - centre
    direction = 1 if median_delta > 0 else -1 if median_delta < 0 else 0
    support = sum(
        abs(delta) >= threshold and (1 if delta > 0 else -1 if delta < 0 else 0) == direction
        for delta in deltas
    )
    reliability, reason = _reliability(len(values), support, mad, threshold)
    return {
        "target": round(target_value, 3),
        "reference_median": round(centre, 3),
        "difference": round(median_delta, 3),
        "unit": unit,
        "per_reference_differences": [round(value, 3) for value in deltas],
        "reference_mad": round(mad, 3),
        "support_count": support,
        "reference_count": len(values),
        "reliability": reliability,
        "reliability_reason": reason,
    }


def _target_outliers(
    target: dict[str, Any],
    baselines: dict[str, float],
    dispersions: dict[str, float],
) -> list[dict[str, Any]]:
    by_band: dict[str, list[dict[str, Any]]] = {}
    for segment in target.get("tonal", {}).get("tonal_timeline", []):
        for band, value in segment.get("band_balance_db", {}).items():
            if band not in baselines:
                continue
            delta = float(value) - baselines[band]
            threshold = max(MIN_TONAL_DELTA_DB, 3.0 * dispersions.get(band, 1.0))
            if abs(delta) >= threshold:
                by_band.setdefault(band, []).append({
                    "time_sec": segment.get("time_sec"),
                    "band": band,
                    "difference_db": round(delta, 2),
                    "detection_threshold_db": round(threshold, 2),
                })
    result: list[dict[str, Any]] = []
    for items in by_band.values():
        items.sort(key=lambda item: abs(item["difference_db"]), reverse=True)
        result.extend(items[:5])
    return sorted(result, key=lambda item: (float(item.get("time_sec") or 0), item["band"]))


def compare_to_references(target: dict[str, Any], references: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not references:
        return None

    target_bands = _bands(target)
    reference_bands = [_bands(item) for item in references]
    tonal: dict[str, dict[str, Any]] = {}
    baselines: dict[str, float] = {}
    dispersions: dict[str, float] = {}

    for band, target_value_raw in target_bands.items():
        values = [float(item[band]) for item in reference_bands if item.get(band) is not None]
        if not values:
            continue
        target_value = float(target_value_raw)
        centre, mad = _median_mad(values)
        deltas = [target_value - value for value in values]
        median_delta = target_value - centre
        direction = 1 if median_delta > 0 else -1 if median_delta < 0 else 0
        support = sum(
            abs(delta) >= MIN_TONAL_DELTA_DB
            and (1 if delta > 0 else -1 if delta < 0 else 0) == direction
            for delta in deltas
        )
        reliability, reason = _reliability(len(values), support, mad, MIN_TONAL_DELTA_DB)
        baselines[band] = centre
        dispersions[band] = max(mad, 0.25)
        tonal[band] = {
            "target_relative_shape_db": round(target_value, 2),
            "reference_median_relative_shape_db": round(centre, 2),
            "difference_db": round(median_delta, 2),
            "per_reference_differences_db": [round(value, 2) for value in deltas],
            "reference_mad_db": round(mad, 2),
            "support_count": support,
            "reference_count": len(values),
            "reliability": reliability,
            "reliability_reason": reason,
        }

    target_lufs = _number(target, "loudness", "integrated_lufs")
    if target_lufs is None:
        target_lufs = _number(target, "loudness", "lufs")
    loudness = _dimension(
        target_lufs,
        references,
        lambda item: _number(item, "loudness", "integrated_lufs")
        if _number(item, "loudness", "integrated_lufs") is not None
        else _number(item, "loudness", "lufs"),
        MIN_LOUDNESS_DELTA_LU,
        "LU",
    )

    dynamics: dict[str, Any] = {}
    for name, path, unit in (
        ("plr", ("loudness", "plr_lu"), "LU"),
        ("short_term_loudness_spread", ("loudness", "short_term_loudness_spread_lu"), "LU"),
        ("crest_factor", ("loudness", "crest_factor_db"), "dB"),
    ):
        result = _dimension(
            _number(target, *path), references, lambda item, p=path: _number(item, *p),
            MIN_DYNAMICS_DELTA, unit,
        )
        if result:
            dynamics[name] = result

    stereo: dict[str, Any] = {}
    for name, path, threshold, unit in (
        ("width", ("stereo", "stereo_width"), MIN_STEREO_WIDTH_DELTA, "ratio"),
        ("phase_correlation", ("stereo", "phase_correlation"), 0.15, "correlation"),
        ("mono_fold_down", ("stereo", "mono_fold_down_loss_db"), 1.0, "dB"),
        ("bass_side_energy", ("stereo", "bass_side_energy_pct"), 10.0, "%"),
    ):
        result = _dimension(
            _number(target, *path), references, lambda item, p=path: _number(item, *p), threshold, unit,
        )
        if result:
            stereo[name] = result

    matching_offsets = []
    if target_lufs is not None:
        for item in references:
            value = _number(item, "loudness", "integrated_lufs")
            if value is None:
                value = _number(item, "loudness", "lufs")
            if value is not None:
                matching_offsets.append(round(target_lufs - value, 2))

    return {
        "source": "references",
        "reference_count": len(references),
        "method": "per-reference-robust-shape-p0",
        "loudness_matching": {
            "applied_to_tonal_shape": True,
            "method": "relative spectral shape (gain invariant)",
            "reference_gain_offsets_to_target_lufs": matching_offsets,
            "note": "Общая громкость исключена из tonal comparison; её разница хранится отдельно.",
        },
        "tonal_shape_difference": tonal,
        "loudness_difference": loudness,
        "dynamics_difference": dynamics,
        "stereo_difference": stereo,
        "outlier_segments": _target_outliers(target, baselines, dispersions),
        "note": "Референсы описывают контекст, а не универсальную норму. Difference не является настройкой плагина.",
    }


def compare_to_genre(
    target: dict[str, Any], genre: str, profiles_dir: str | Path = "data/genre-curves",
) -> dict[str, Any] | None:
    """Genre data is context only and never enters the P0 recommendation engine."""
    profile_path = Path(profiles_dir) / f"{genre}.json"
    if not profile_path.exists():
        return None
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile.get("relative_band_db", {})
    bands = _bands(target)
    return {
        "source": "genre-profile",
        "reference_count": 0,
        "method": "exploratory-profile-context-only",
        "profile_version": profile.get("version", "unknown"),
        "genre_context": {
            key: round(float(bands[key]) - float(expected[key]), 2)
            for key in bands.keys() & expected.keys()
        },
        "note": "Экспериментальный жанровый контекст. Он не является нормой и не создаёт рекомендаций.",
    }
