# SoundDebug release map

Update this ledger with every handoff.

## Current releases

| Release | Target | State | Exit criterion |
|---|---:|---|---|
| `mvp-0.1.0` | 11 Aug | Complete | Upload → worker → stored report E2E passed on host |
| `mvp-0.2.0-evidence` | 16 Aug | Code complete; host gate | Real WAV/MP3 reports are understandable and contain no unsafe exact-EQ claims |
| `beta-0.3.0` | 23 Aug | Planned | Public URL, 10 pilot users, feedback per diagnosis, no launch blocker |
| `beta-0.4.0` | Sep | Research | Calibrated rule precision and Audio ML/MAEST decision |

## 12-day delivery plan

| Date | Deliverable | State |
|---|---|---|
| 11 Aug | Baseline E2E, auth/worker hotfixes | Done |
| 12 Aug | DSP v2 representation, reference median/MAD | Done |
| 13 Aug | Evidence diagnostics and report UI | Done in code |
| 14 Aug | Docker/Blazor build, WAV + MP3 host checks | Host action |
| 15 Aug | Test three real tracks with 1–3 references | Pending |
| 16 Aug | Freeze `mvp-0.2.0-evidence` | Pending |
| 17–18 Aug | Fix confirmed false positives and UI blockers only | Pending |
| 19 Aug | Staging HTTPS and retention/error check | Pending |
| 20 Aug | Pilot with 3–5 producers; collect per-diagnosis feedback | Pending |
| 21 Aug | Triage feedback; hide low-precision rules | Pending |
| 22 Aug | Release candidate smoke/E2E; feature freeze | Pending |
| 23 Aug | Tag/open first beta | Pending |

## Delivered in evidence v2

- Spectral energy shares and level-independent centred log-ratios.
- Per-reference robust comparison with median/MAD, explicit support counts, textual reliability and timestamps.
- Gated loudness timeline, P95–P10 short-term spread (not labelled EBU LRA), PLR, clipping regions and DC offset.
- Local stereo phase risk, mono fold-down loss and low-band Side share.
- Evidence-based diagnosis schema and comprehensible Blazor report.
- Demucs removed from active release.
- Optional Audiobox Aesthetics worker, isolated from deterministic DSP.
- Local analysis CLI, Windows/Linux scripts, research note and experiment log.

## Host gate for 0.2.0

1. `docker compose build --no-cache frontend dsp-worker upload-service`.
2. `docker compose up -d --force-recreate` and `./scripts/smoke-test.ps1`.
3. `python ./tests/test_api.py`; confirm `report_version=mvp-2-evidence`.
4. Analyse a real stereo WAV with no references: no tonal recommendations should appear.
5. Analyse the same WAV with two references: reference deltas and timestamps should appear.
6. Analyse one MP3 and confirm cleanup/history/report UI.
7. Optionally run `./scripts/start-audio-ml.ps1`, then check one PQ prediction.

## Deferred until evidence exists

- Demucs/RoFormer and instrument-specific diagnosis.
- MAEST genre/reference embeddings.
- Learned ranking or LLM-written recommendations.
- Calibrated genre profiles and automatic genre selection.
- GPU autoscaling, billing, teams and multi-region storage.
