# Changelog

## [Unreleased] — MVP target 2026-08-23

### Added

- One-origin Blazor + API production deployment.
- Five aligned genres and up to three reference tracks.
- 4× oversampled, per-channel true-peak estimate and loudness-range indicator.
- Reference-conditioned tonal, loudness and stereo comparison.
- Optional Demucs `htdemucs` four-stem analysis.
- Failed-job UI, 2-second polling and structured report sections.
- Upload limits and post-analysis deletion of source/reference audio.
- Release setup, start, smoke-test and GitHub preparation scripts.
- Per-report feedback and deletion of analyses from user history.

### Fixed

- Protected the upload page from anonymous access and return users to it after
  login instead of sending an empty Bearer token and exposing `Missing token`.
- Attach JWT authorization per frontend request and handle expired sessions with
  a clear re-login flow.
- Fixed DSP worker startup by copying the reference and stem worker packages
  required by its imports into the Docker image.
- Smoke tests now detect an unavailable Celery worker before E2E jobs remain
  indefinitely at `pending 0%`.
- Added a Docker build-context ignore list for secrets, Git metadata, caches and
  generated frontend artefacts.

### Security

- Removed committed `.env` and generated build output.
- Closed public report writes and added an internal service token.
- Only the web frontend publishes a host port.

### Known MVP limitations

- Demucs runs on CPU in the default Compose profile.
- LRA is a documented short-term P95–P10 estimate, not the final gated EBU implementation.
- Genre profiles are fallback guidance; user references take priority.
- No email verification, password reset, admin panel or analytics dashboard yet.
