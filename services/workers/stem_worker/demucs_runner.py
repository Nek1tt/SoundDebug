"""Small, replaceable Demucs adapter used by the MVP worker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from services.workers.dsp_worker.analyzer import analyze


def separate_and_analyze(
    audio_path: str | Path,
    output_root: str | Path,
    model: str = "htdemucs",
) -> dict[str, Any]:
    audio_path = Path(audio_path)
    output_root = Path(output_root)
    command = [
        sys.executable,
        "-m",
        "demucs.separate",
        "--name",
        model,
        "--out",
        str(output_root),
        str(audio_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        message = completed.stderr.strip()[-1200:] or completed.stdout.strip()[-1200:]
        raise RuntimeError(f"Demucs failed: {message}")

    stem_dir = output_root / model / audio_path.stem
    stems: dict[str, Any] = {}
    for stem_name in ("vocals", "drums", "bass", "other"):
        stem_path = stem_dir / f"{stem_name}.wav"
        if not stem_path.exists():
            continue
        metrics = analyze(stem_path)
        stems[stem_name] = {
            "lufs": metrics["loudness"]["lufs"],
            "true_peak_db": metrics["loudness"]["true_peak_db"],
            "crest_factor_db": metrics["loudness"]["crest_factor_db"],
            "band_energy_db": metrics["tonal"]["band_energy_db"],
        }

    if not stems:
        raise RuntimeError(f"Demucs produced no stems in {stem_dir}")

    return {
        "enabled": True,
        "model": model,
        "stems": stems,
        "disclaimer": "Stem metrics are estimates; separation artefacts can affect the diagnosis.",
    }
