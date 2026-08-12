# GitHub handoff

The archive is based on `Nek1tt/SoundDebug` branch `release/mvp`, commit:

```text
cf7e35742277fc3f074c80d6f1fd142c312f14d8
```

## Apply in a clean clone (Windows)

```powershell
git clone --branch release/mvp --single-branch https://github.com/Nek1tt/SoundDebug.git
cd SoundDebug
git switch -c release/mvp-evidence-v2
```

Extract the contents of the delivered `SoundDebug-evidence-v2` folder over the repository root. Keep the `.git` directory from the clone.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup.ps1
docker compose build --no-cache frontend upload-service dsp-worker
docker compose up -d --force-recreate
./scripts/smoke-test.ps1
python -m pip install -r requirements-dev.txt
python ./tests/test_api.py
git add -A
git status
git commit -m "feat: add evidence-based SoundDebug analysis v2"
git push -u origin release/mvp-evidence-v2
```

Create a pull request from `release/mvp-evidence-v2` to `release/mvp` after the real WAV/MP3 host checks in `docs/RELEASE_MAP.md` pass.

## Important rebuild boundary

At minimum these images changed:

- `frontend`;
- `upload-service`;
- `dsp-worker`.

A restart without `docker compose build` leaves the v1 analysis code active.

## Optional Audio ML

Do not enable it for the first deterministic smoke test. Afterwards:

```powershell
./scripts/start-audio-ml.ps1
```

The first build and checkpoint download are substantially larger than the base worker.
