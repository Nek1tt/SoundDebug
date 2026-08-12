# Experiment log

## 2026-08-12 — P0 trustworthy diagnostics

The P0 regression suite passed 15/15 tests. It verifies per-reference support rather than pooled segment counts, strict finding classes, full-card fields, maximum-three prioritisation, dual-mono detection, P95–P10 naming, and absence of direct plugin settings.

The synthetic DSP suite passed with band shares `99.999%`, gain change `0.000000` percentage points, injected 48 Hz sub-bass change `44.847` percentage points, local phase correlation minimum `−0.3333`, clipping count `0 → 200`, and no generated EQ/Q setting. These checks validate semantics and regression invariants, not perceptual accuracy.

## 2026-08-11 — DSP v2 synthetic invariants

Command:

```bash
python experiments/run_dsp_v2_synthetic.py
```

Machine-readable result: [`docs/experiments/dsp-v2-synthetic-2026-08-11.json`](experiments/dsp-v2-synthetic-2026-08-11.json).

| Check | Result | Interpretation |
|---|---:|---|
| Sum of band shares | 99.999% | New UI percentages are coherent |
| Max share change after −20 dB gain | 0.000000 pp | Tonal profile is level-independent |
| 48 Hz injection: sub-bass share | +44.847 pp | Intended band change is detected |
| Local anti-phase | min correlation −0.3333; 2 segments | Risk is localised rather than hidden in one track average |
| Injected clipping | 0 → 200 samples | Technical defect is detected |
| Direct delta copied into EQ | false | Diagnostic wording respects the v2 safety contract |

This is a regression/sanity experiment, not evidence of perceptual accuracy. The next meaningful experiment requires real mixes, suitable references and human labels.

## Unit and contract checks

- 9/9 Python unit tests passed.
- API keeps v1 aliases for migration while emitting `report_version=mvp-2-evidence`.
- Docker, Blazor and real-audio E2E must be confirmed on the deployment host.
