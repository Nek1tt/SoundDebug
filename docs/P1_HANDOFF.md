# P1 handoff

The archive is a complete project tree based on `release/mvp` commit `c021832`.

## Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/start-p1.ps1
./scripts/verify-p1.ps1
```

No local Python or .NET SDK is used. Both commands run the application and verification through Docker.

If Docker Desktop registry DNS is unavailable but all P0 base images are cached:

```powershell
./scripts/start-p1.ps1 -Offline
./scripts/verify-p1.ps1 -Offline
```

Preserve `.env` when reusing the existing `postgres_data` volume. Never delete the volume merely to work around a password mismatch unless losing users and reports is acceptable.

## Verification result expected

The final line of `verify-p1.ps1` is printed only after image builds, service health, migration, containerized tests, a real WAV upload, worker completion, report contract, temporal region/card linkage, feedback, and job deletion all succeed.
