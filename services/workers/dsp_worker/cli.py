"""Local/Docker CLI for repeatable SoundDebug experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyzer import analyze
from .audio_ml import analyse_audio_ml
from .report_builder import build_report
from services.workers.reference_worker.curve_matcher import compare_to_genre, compare_to_references


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse one finished mix without starting the web stack")
    parser.add_argument("track", type=Path)
    parser.add_argument("--reference", action="append", default=[], type=Path)
    parser.add_argument("--genre", default="electronic", choices=["lo-fi", "modern-pop", "hip-hop", "techno", "electronic"])
    parser.add_argument("--audio-ml", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("analysis-report.json"))
    args = parser.parse_args()

    metrics = analyze(args.track)
    reference_metrics = [analyze(path, include_rhythm=False) for path in args.reference]
    comparison = compare_to_references(metrics, reference_metrics) or compare_to_genre(metrics, args.genre)
    audio_ml = analyse_audio_ml(args.track, requested=args.audio_ml)
    report = build_report(
        metrics, args.genre, comparison, audio_ml,
        uses_user_references=bool(args.reference),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {args.output}")
    print(
        f"Main recommendations: {len(report['recommendations'])}; "
        f"additional findings: {len(report['additional_findings'])}; "
        f"references: {len(args.reference)}; Audio ML: {audio_ml.get('enabled')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
