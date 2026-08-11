"""Explainable comparison between a target mix and one or more references."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any


def compare_to_references(target: dict[str, Any], references: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not references:
        return None

    target_bands = target.get("tonal", {}).get("band_energy_db", {})
    reference_bands = [item.get("tonal", {}).get("band_energy_db", {}) for item in references]
    tonal_delta: dict[str, float] = {}
    reference_median: dict[str, float] = {}

    for band, value in target_bands.items():
        values = [bands.get(band) for bands in reference_bands if bands.get(band) is not None]
        if value is None or not values:
            continue
        baseline = float(median(values))
        reference_median[band] = round(baseline, 2)
        tonal_delta[band] = round(float(value) - baseline, 2)

    target_lufs = target.get("loudness", {}).get("lufs")
    lufs_values = [
        item.get("loudness", {}).get("lufs")
        for item in references
        if item.get("loudness", {}).get("lufs") is not None
    ]

    target_width = target.get("stereo", {}).get("stereo_width")
    width_values = [
        item.get("stereo", {}).get("stereo_width")
        for item in references
        if item.get("stereo", {}).get("stereo_width") is not None
    ]

    return {
        "source": "references",
        "reference_count": len(references),
        "reference_band_median_db": reference_median,
        "tonal_delta_db": tonal_delta,
        "lufs_delta": (
            round(float(target_lufs) - float(median(lufs_values)), 2)
            if target_lufs is not None and lufs_values else None
        ),
        "stereo_width_delta": (
            round(float(target_width) - float(median(width_values)), 3)
            if target_width is not None and width_values else None
        ),
        "note": "Positive tonal values mean the target has more energy than the reference median.",
    }


def compare_to_genre(
    target: dict[str, Any],
    genre: str,
    profiles_dir: str | Path = "data/genre-curves",
) -> dict[str, Any] | None:
    """Fallback comparison using a versioned, deliberately conservative profile."""
    profile_path = Path(profiles_dir) / f"{genre}.json"
    if not profile_path.exists():
        return None
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile.get("relative_band_db", {})
    bands = target.get("tonal", {}).get("band_energy_db", {})
    finite_values = [float(value) for value in bands.values() if value is not None]
    if not finite_values:
        return None
    centre = float(median(finite_values))
    target_relative = {key: float(value) - centre for key, value in bands.items() if value is not None}
    delta = {
        key: round(target_relative[key] - float(expected[key]), 2)
        for key in target_relative.keys() & expected.keys()
    }
    return {
        "source": "genre-profile",
        "reference_count": 0,
        "profile_version": profile.get("version", "unknown"),
        "tonal_delta_db": delta,
        "lufs_delta": None,
        "stereo_width_delta": None,
        "note": profile.get("disclaimer", "Genre profile is fallback guidance only."),
    }
