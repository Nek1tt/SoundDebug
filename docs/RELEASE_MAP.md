# SoundDebug release map

This file is the mandatory release ledger. Update **Current state**, **Delivered** and **Next release** with every release or handoff.

## Current state

| Release | Target | State | Exit criterion |
|---|---:|---|---|
| `mvp-0.1.0` | 23 Aug 2026 | Implementation complete; host verification required | A new user can upload a track and receive a report through the public URL |
| `beta-0.2.0` | Sep 2026 | Planned | 100 completed analyses, feedback captured, top failures fixed |
| `beta-0.3.0` | Oct 2026 | Planned | GPU stem worker, better masking evidence, operational dashboard |
| `1.0.0` | After beta evidence | Deferred | Stable quality thresholds, retention controls and documented SLA |

## 12-day launch plan

| Date | Deliverable | State |
|---|---|---|
| 12 Aug | Clean integration branch, secrets/build artefacts removed | Done |
| 13 Aug | One API origin, aligned auth/jobs/report contract | Done |
| 14 Aug | Five genres, file validation and stable failure states | Done |
| 15 Aug | Corrected channel-aware oversampled true peak + LRA indicator | Done |
| 16 Aug | Real upload and comparison of 1–3 references | Done |
| 17 Aug | Demucs adapter and optional four-stem report | Done |
| 18 Aug | Report UI: DSP, tonal, stereo, reference and stem evidence | Done |
| 19 Aug | Production Compose, Nginx and internal-only services | Done |
| 20 Aug | Unit tests, frontend build and Compose validation | In progress |
| 21 Aug | Staging host smoke test with WAV, MP3 and failed input | Host action |
| 22 Aug | Fix only launch blockers; freeze features | Pending |
| 23 Aug | Tag `v0.1.0`, open the first beta | Pending |

## Delivered in this handoff

- Complete vertical slice from upload through report.
- Reference-conditioned comparison instead of genre-only claims.
- Demucs behind a user-controlled beta checkbox.
- Privacy cleanup of original uploads.
- Internal token for worker report writes.
- One-command Compose deployment and repeatable scripts.
- User feedback capture and deletion of saved analyses.

## Launch blockers that require the deployment host

- Build Docker images with unrestricted access to Microsoft/Python package registries.
- Let Demucs download `htdemucs` once and retain its cache volume.
- Run one real stereo WAV and one MP3 end to end.
- Configure domain and HTTPS at the hosting edge.
- Rotate any secrets that were ever used from the old committed `.env`.

## Next release (`beta-0.2.0`)

- Feedback summary for beta triage and explicit retention settings.
- Strict EBU Tech 3342 loudness-range implementation.
- Calibrated genre profiles from a licensed dataset.
- Better time-localized evidence and downloadable JSON/PDF report.
- CI integration test that boots Compose and analyses a fixture.

## Deferred from MVP by design

- MAEST/music embeddings, automatic genre selection and aesthetic scoring.
- LLM-written diagnoses.
- RoFormer benchmark and GPU autoscaling.
- Billing, teams, social login and multi-region storage.
