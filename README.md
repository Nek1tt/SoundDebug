# SoundDebug P1 — Temporal Audio Debugger

SoundDebug analyses a finished mix and answers two separate questions:

1. What is measured, and how reliable is the conclusion?
2. Where in the track should the user listen more carefully, and why?

P1 preserves the P0 `FACT`, `REFERENCE_DIFFERENCE`, and `HYPOTHESIS` contract and adds a temporal pipeline. It does not infer verse/chorus/drop labels and never converts a measured delta into an EQ, compressor, gain, or stereo-width setting.

## Requirements

Only Docker Desktop (or Docker Engine) with Compose v2 is required. Do not install Python or .NET on the host.

Recommended resources: 6 GB RAM and 5 GB free disk space.

## Clean Windows launch

Keep the existing `.env` if P0 already uses a PostgreSQL volume. Do not run `docker compose down -v` unless you intentionally want to delete users and reports.

```powershell
cd C:\SoundDebug
Set-ExecutionPolicy -Scope Process Bypass

./scripts/start-p1.ps1
```

The script performs Docker registry preflight, creates `.env` only when it is absent, builds every image, starts the stack, checks the Celery worker and waits for HTTP health.

Open <http://localhost:8080> or the `PUBLIC_PORT` configured in `.env`.

### If Docker Desktop currently has no DNS/network access

Run the preflight alone:

```powershell
./scripts/docker-preflight.ps1
```

If it cannot pull `python`, `nginx`, or the .NET SDK image, fix Docker Desktop DNS/proxy and restart Docker Desktop. This failure happens before SoundDebug code is built.

If all required base images are already cached from P0, an offline build can be attempted without registry access:

```powershell
./scripts/start-p1.ps1 -Offline
```

Offline mode fails clearly when even one required image is missing.

## Full Docker-only verification

```powershell
./scripts/verify-p1.ps1
```

This command uses containers for every check. It verifies:

- registry access or the explicit offline cache;
- all six project image builds;
- Compose startup and service health;
- database migration exit code;
- Celery worker queue connectivity;
- Python unit and synthetic DSP tests inside the worker image;
- registration, login, upload, processing, P1 report retrieval, feedback, and deletion through the public API;
- a real generated 20-second stereo WAV containing a local phase problem;
- temporal windows, a merged region, linked diagnostic card, and `where_to_listen` procedure.

Use cached images when Docker has no network:

```powershell
./scripts/verify-p1.ps1 -Offline
```

Use `-NoCache` only when debugging a suspected stale build; it is not required for a normal update.

## P1 analysis contract

- Window: 6 seconds.
- Hop: 1.5 seconds.
- Per-window features: loudness, RMS, crest factor, dynamics spread, transient density, spectral centroid/rolloff/flatness/bandwidth, seven relative tonal bands, Mid/Side energy, stereo width, phase correlation, mono fold-down loss, and low-frequency Side energy.
- Local evidence: robust comparison with surrounding windows.
- Reference evidence: every reference is one independent vote against its own temporal distribution.
- Adjacent overlapping detections of the same category are merged before reporting.
- Ranking uses magnitude, duration, confirming metrics, and reference stability.
- A public region always has a linked diagnostic card.
- The comparison region never overlaps the anomalous region.
- The main report remains limited to three priority cards; the rest remain available as additional findings.

## Timeline workflow

1. Upload a mix and optionally up to three references.
2. Open the report timeline.
3. Click a marker to show its linked diagnostic card immediately.
4. Follow `Где слушать`: audition the region in stereo, then mono when relevant, and compare it with the nearest non-overlapping stable region.
5. Find the first source or bus where the change appears by bypassing one stage at a time.
6. Export a short revision, loudness-match it, and repeat the A/B comparison.

The waveform shown in the report is a derived envelope. The source file and reference uploads remain transient and are deleted after processing.

## Analyse a file without the website

The CLI also runs inside Docker:

```powershell
./scripts/analyze.ps1 `
  -Track "C:\Music\mix.wav" `
  -Genre techno `
  -Reference "C:\Music\ref-1.wav","C:\Music\ref-2.wav","C:\Music\ref-3.wav"
```

The report is written to `analysis-output/report.json`.

## Architecture

```text
Browser -> Nginx/Blazor -> Gateway -> Auth / Upload / Report
                                Upload -> Redis -> DSP P1 worker
                                          Worker -> PostgreSQL report
                                Audio -> MinIO -> deleted after processing
```

Only the frontend port is public. PostgreSQL, Redis, MinIO, and backend services stay inside the Compose network.

Implementation details are in [docs/P1_TEMPORAL_DEBUGGER.md](docs/P1_TEMPORAL_DEBUGGER.md). The P0 semantic guarantees remain documented in [docs/P0_TRUSTWORTHY_DIAGNOSTICS.md](docs/P0_TRUSTWORTHY_DIAGNOSTICS.md).
