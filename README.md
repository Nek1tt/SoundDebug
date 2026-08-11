# SoundDebug MVP

SoundDebug analyses a finished mix and returns an explainable technical health report: loudness, true peak, dynamics, tonal balance, stereo/phase, rhythm, reference deltas and optional Demucs stem metrics.

## First launch

Requirements: Docker Desktop / Docker Engine with Compose v2, at least 8 GB RAM and 10 GB free disk space. The first Demucs build and first model download take longer than later runs.

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup.ps1
./scripts/start.ps1
./scripts/smoke-test.ps1
python -m pip install -r requirements-dev.txt
python ./tests/test_api.py
```

Open <http://localhost:8080> (or the port selected in `.env`).

### Linux / macOS

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/start.sh
./scripts/smoke-test.sh
python3 -m pip install -r requirements-dev.txt
python3 ./tests/test_api.py
```

## MVP flow

1. Register or sign in.
2. Upload one WAV, MP3, FLAC, OGG or M4A file (up to 50 MB / 15 minutes).
3. Select one of five genres.
4. Optionally add up to three references.
5. Optionally enable Demucs beta. CPU separation can take several minutes.
6. Wait for the report and inspect evidence before applying any recommendation.

Uploaded source and reference files are removed after processing. Derived report metrics remain in PostgreSQL.

## Architecture

Only the frontend port is public. Nginx serves Blazor and proxies `/api` to the gateway. PostgreSQL, Redis, MinIO and all backend services stay inside the Compose network.

```text
Browser -> Nginx/Blazor -> Gateway -> Auth / Upload / Report
                                Upload -> Redis -> DSP + Demucs worker
                                          Worker -> Report
```

## Operations

```bash
docker compose ps
docker compose logs -f dsp-worker
docker compose restart dsp-worker
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to delete users, reports, queues, object storage and the Demucs model cache.

For a public server, put Caddy, Traefik or the hosting provider's HTTPS proxy in front of `PUBLIC_PORT`; never expose PostgreSQL, Redis or MinIO directly.

## Development

Backend unit tests:

```bash
python -m pytest tests -q
```

Frontend build:

```bash
dotnet build frontend/SoundDebug.Frontend/SoundDebug.Frontend.csproj
```

Release scope, daily checklist and deferred features are tracked in [docs/RELEASE_MAP.md](docs/RELEASE_MAP.md). Every release must update that file and [CHANGELOG.md](CHANGELOG.md).
