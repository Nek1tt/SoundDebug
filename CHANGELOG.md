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

### Security

- Removed committed `.env` and generated build output.
- Closed public report writes and added an internal service token.
- Only the web frontend publishes a host port.

### Known MVP limitations

- Demucs runs on CPU in the default Compose profile.
- LRA is a documented short-term P95–P10 estimate, not the final gated EBU implementation.
- Genre profiles are fallback guidance; user references take priority.
- No email verification, password reset, admin panel or analytics dashboard yet.
