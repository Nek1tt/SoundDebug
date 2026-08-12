# P0 implementation handoff

Baseline: `release/mvp` commit `cf7e35742277fc3f074c80d6f1fd142c312f14d8`, with the previously delivered evidence-v2/auth-compatible changes preserved.

## Verification completed in the build environment

- Python compile check: passed.
- Unit suite: 15/15 passed.
- Reference agreement regression: `1/3` stays `LOW` and does not become a confident hypothesis.
- Reference consensus regression: consistent `3/3` can become `HIGH` reliability.
- Full CLI analysis: target plus three WAV references passed.
- Main report contract: maximum three recommendations, all other findings retained.
- Finding class invariant: only `FACT`, `REFERENCE_DIFFERENCE`, or `HYPOTHESIS`.
- JSON validation: passed.
- Shell syntax validation: passed.
- `pip check`: passed.
- `git diff --check`: passed.
- Synthetic DSP experiment: passed all six checks.

Synthetic results are stored in `docs/experiments/p0-synthetic-2026-08-12.json`.

## Required host gate

Docker and .NET SDK were not present in the build environment. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/verify-p0.ps1
./scripts/start-p0.ps1
./scripts/smoke-test.ps1
python ./tests/test_api.py
```

Then analyse a real mix with three relevant references and inspect:

- whether the main report contains at most three cards;
- whether each card has the full diagnostic procedure;
- whether support such as `2/3` matches the individual references;
- whether old reports are clearly distinguishable from `p0-trustworthy-diagnostics-1` reports;
- whether the layout is usable on desktop and mobile.

## Build note

A container restart is insufficient because P0 changes both Python worker code and Blazor UI. Rebuild at least `dsp-worker`, `upload-service`, and `frontend`.
