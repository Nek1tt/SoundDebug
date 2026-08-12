"""Optional Audiobox Aesthetics adapter.

This dependency is isolated from the deterministic DSP image.  Its scores are
subjective model predictions and must never override measurable evidence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from shared.config import AUDIO_ML_CHECKPOINT, AUDIO_ML_ENABLED

logger = logging.getLogger(__name__)
_predictor: Any = None


def _normalise_scores(raw: Any) -> dict[str, float]:
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key in ("PQ", "PC", "CE", "CU"):
        value = raw.get(key)
        if value is not None:
            result[key] = round(float(value), 3)
    return result


def analyse_audio_ml(path: str | Path, requested: bool = False) -> dict[str, Any]:
    if not requested:
        return {"enabled": False, "reason": "not requested", "backend": "audiobox-aesthetics"}
    if not AUDIO_ML_ENABLED:
        return {
            "enabled": False,
            "reason": "Audio ML image is not active; use scripts/start-audio-ml.*",
            "backend": "audiobox-aesthetics",
        }

    try:
        from audiobox_aesthetics.infer import initialize_predictor
    except ImportError as exc:
        logger.warning("Audiobox Aesthetics is unavailable: %s", exc)
        return {"enabled": False, "reason": "audiobox_aesthetics package is unavailable", "backend": "audiobox-aesthetics"}

    global _predictor
    try:
        if _predictor is None:
            _predictor = initialize_predictor(ckpt=AUDIO_ML_CHECKPOINT)
        scores = _normalise_scores(_predictor.forward([{"path": str(path)}]))
        if not scores:
            raise RuntimeError("model returned no recognised axes")
        return {
            "enabled": True,
            "backend": "audiobox-aesthetics",
            "scores": scores,
            "scale": "model prediction, approximately 1–10",
            "caveat": "Subjective no-reference prediction; compare versions, do not treat it as a technical verdict.",
        }
    except Exception as exc:
        logger.exception("Audio ML inference failed")
        return {"enabled": False, "reason": f"inference failed: {type(exc).__name__}", "backend": "audiobox-aesthetics"}
