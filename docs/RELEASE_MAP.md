# SoundDebug release map

## Current releases

| Release | State | Exit criterion |
|---|---|---|
| `mvp-0.1.0` | Complete | Upload → worker → stored report E2E |
| `p0-trustworthy-diagnostics` | Complete | Honest finding classes, reference support, educational cards |
| `p1-temporal-debugger` | Code complete | Docker-only verification and real-track pilot |
| `beta-0.3.0` | Planned | Public URL, pilot users, no launch blocker |

## P1 delivered

- Synchronized overlapping feature windows.
- Local and reference-distribution anomaly evidence.
- Meaningful-region merging and deterministic ranking.
- Non-overlapping stable A/B comparison region.
- Timeline markers linked to complete diagnostic cards.
- Docker-only startup and verification; no host Python/.NET dependency.

## Required acceptance on a Docker host

1. Run `./scripts/verify-p1.ps1`.
2. Confirm every image builds and every service becomes healthy.
3. Confirm `db-migrate` exits with code 0.
4. Confirm the generated real stereo WAV completes through the public API.
5. Confirm `report_version=p1-temporal-debugger-1`.
6. Confirm at least one merged region, its linked card, and `where_to_listen`.
7. Analyse three real mixes with 1–3 references and inspect false positives before beta.

## Deferred

- Semantic section recognition and cross-song section alignment.
- Demucs/RoFormer and instrument-specific diagnosis.
- Learned ranking or generated recommendations.
- Calibrated genre profiles and automatic genre selection.
- Production hosting, GPU autoscaling, billing and teams.
