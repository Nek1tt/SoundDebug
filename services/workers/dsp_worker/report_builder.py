"""Single P1 report assembly path shared by Celery and the local CLI."""

from __future__ import annotations

from typing import Any

from .recommendations import generate_findings, split_priority_findings


def build_report(
    metrics: dict[str, Any], genre: str, comparison: dict[str, Any] | None,
    audio_ml: dict[str, Any] | None, *, uses_user_references: bool,
    temporal_regions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings = generate_findings(metrics, genre, comparison, audio_ml, temporal_regions)
    recommendations, additional = split_priority_findings(findings, limit=3)
    temporal = metrics.get("temporal", {})
    public_metrics = {key: value for key, value in metrics.items() if key != "temporal"}
    technical_details = {
        "source": metrics.get("meta", {}),
        "loudness": metrics.get("loudness", {}),
        "tonal": metrics.get("tonal", {}),
        "stereo": metrics.get("stereo", {}),
        "rhythm": metrics.get("rhythm", {}),
        "temporal": {
            "window_sec": temporal.get("window_sec"),
            "hop_sec": temporal.get("hop_sec"),
            "window_count": len(temporal.get("windows", [])),
            "method": temporal.get("method"),
        },
        "measurement_notes": [
            "True peak is a practical 4x oversampled estimate.",
            "P95-P10 short-term loudness spread is not labelled as certified EBU LRA.",
            "Tonal values are relative spectral shape and energy shares, not EQ settings.",
            "Genre profiles are exploratory context, not universal targets.",
        ],
    }
    return {
        **public_metrics,
        "genre": genre,
        "reference_comparison": comparison,
        "audio_ml": audio_ml or {"enabled": False},
        "temporal_analysis": {
            **temporal,
            "regions": temporal_regions or [],
            "region_count": len(temporal_regions or []),
            "note": "Regions show where evidence changes; they do not name song sections or prescribe plugin settings.",
        },
        "recommendations": recommendations,
        "additional_findings": additional,
        "all_findings": findings,
        "technical_details": technical_details,
        "diagnostic_summary": {
            "total": len(findings),
            "main_recommendations": len(recommendations),
            "additional_findings": len(additional),
            "facts": sum(item["classification"] == "FACT" for item in findings),
            "reference_differences": sum(item["classification"] == "REFERENCE_DIFFERENCE" for item in findings),
            "hypotheses": sum(item["classification"] == "HYPOTHESIS" for item in findings),
            "uses_user_references": uses_user_references,
        },
        "report_version": "p1-temporal-debugger-1",
        "artistic_intent_warning": (
            "SoundDebug separates directly measured facts, differences from your references and hypotheses. "
            "Only hypotheses ask for an audition; no measured difference is a plugin setting."
        ),
    }
