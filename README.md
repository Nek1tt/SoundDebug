# SoundDebug MVP — P0 trustworthy diagnostics

Current diagnostic contract: **P0 — Trustworthy Diagnostic Engine**. See [docs/P0_TRUSTWORTHY_DIAGNOSTICS.md](docs/P0_TRUSTWORTHY_DIAGNOSTICS.md) for finding classes, reference reliability, launch scripts, and verification.

SoundDebug analyses a finished mix and separates three different things:

1. **Measurements** — loudness, true-peak estimate, dynamics, spectral energy and stereo/mono compatibility.
2. **Comparison** — robust differences from 1–3 user references after level-independent normalisation.
3. **Diagnostics** — classified facts, reference differences and testable hypotheses with evidence, textual reliability and an ordered DAW check.

A spectral delta is not copied into an EQ gain. Genre is context, not a mandatory LUFS target. Demucs is outside this release.

## First launch

Requirements: Docker Desktop / Docker Engine with Compose v2, 6 GB RAM and 5 GB free disk space.

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup.ps1
./scripts/start-p0.ps1
./scripts/smoke-test.ps1
python -m pip install -r requirements-dev.txt
python ./tests/test_api.py
```

### Linux / macOS

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/start-p0.sh
./scripts/smoke-test.sh
python3 -m pip install -r requirements-dev.txt
python3 ./tests/test_api.py
```

Open <http://localhost:8080> (or `PUBLIC_PORT` from `.env`).

## Recommended analysis flow

1. Upload a WAV, MP3, FLAC, OGG or M4A mix (up to 50 MB / 15 minutes).
2. Select a genre for report context.
3. Preferably add 1–3 references that represent the intended sound.
4. Read technical faults first, then reference observations.
5. Audition the indicated timestamps with loudness-matched A/B in the DAW.
6. Change one thing, export again and compare the reports.

Without references SoundDebug still detects technical delivery and mono-compatibility risks, but does not issue tonal EQ advice. Uploaded audio is deleted after processing; derived report data remains in PostgreSQL.

## What the metrics mean

| Metric | Meaning | Does not prove |
|---|---|---|
| Integrated LUFS | Gated perceived programme loudness | Correct genre loudness |
| True peak estimate | 4× oversampled maximum, per channel | Certified conformance of a delivery file |
| PLR | Difference between true peak and integrated loudness | Overcompression by itself |
| P95–P10 short-term spread | Gated spread of 3 s short-term values; explicitly not certified EBU LRA | Whether the arrangement is expressive |
| Band energy % | Share of 20 Hz–20 kHz analysed power | Required EQ gain |
| Reference delta | Centred log-ratio vs median/MAD of references | A mastering instruction |
| L/R correlation | Similarity of channels over time | Stereo quality by itself |
| Mono fold-down loss | RMS change when L/R are folded to mono | Audibility without listening |

## Analyse a file without the website

The base command writes `analysis-output/report.json`:

```powershell
./scripts/analyze.ps1 -Track "C:\music\mix.wav" -Genre techno
./scripts/analyze.ps1 -Track "C:\music\mix.wav" -Genre techno `
  -Reference "C:\music\ref-1.wav","C:\music\ref-2.wav"
```

```bash
./scripts/analyze.sh ./mix.wav techno ./ref-1.wav ./ref-2.wav
```

## Optional Audio ML beta

The extended worker integrates Meta Audiobox Aesthetics. Only `Production Quality` is surfaced as an uncalibrated secondary signal; it never creates a technical verdict or invented confidence.

```powershell
./scripts/start-audio-ml.ps1
```

or for one local experiment:

```powershell
./scripts/analyze.ps1 -Track "C:\music\mix.wav" -Genre electronic -AudioML
```

The first build/model download is large. The deterministic DSP image remains the default.

## Architecture

```text
Browser -> Nginx/Blazor -> Gateway -> Auth / Upload / Report
                                Upload -> Redis -> DSP v2 worker
                                          Worker -> Report
```

Only the frontend port is public. PostgreSQL, Redis, MinIO and backend services remain inside the Compose network.

## Verification

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python experiments/run_dsp_v2_synthetic.py
docker compose config --quiet
./scripts/verify-p0.sh
```

Research decisions are documented in [docs/RESEARCH_2026.md](docs/RESEARCH_2026.md), experiment results in [docs/EXPERIMENT_LOG.md](docs/EXPERIMENT_LOG.md), and release scope in [docs/RELEASE_MAP.md](docs/RELEASE_MAP.md).
