# Changelog

## P1 — Temporal Audio Debugger (2026-08-12)

- Added synchronized 6-second temporal windows with a 1.5-second hop.
- Added loudness, dynamics, tonal/spectral, M/S, stereo, phase, mono-loss and transient features per window.
- Added robust local and per-reference temporal-distribution evidence.
- Added merging and ranking by magnitude, duration, confirming metrics and reference stability.
- Added non-overlapping stable comparison regions.
- Added a derived waveform timeline and immediate marker-to-card selection.
- Added `Где слушать` procedures without direct plugin settings.
- Preserved all P0 finding classes and the three-card main-report limit.
- Added Docker-only preflight, online/offline startup, containerized unit tests and public API E2E verification.

## P0 — Trustworthy Diagnostic Engine (2026-08-12)

- Added the strict `FACT`, `REFERENCE_DIFFERENCE`, and `HYPOTHESIS` finding classes.
- Replaced short recommendation snippets with full educational diagnostic cards.
- Rebuilt reference comparison around independent per-track support instead of pooled segment counts.
- Separated loudness, relative tonal shape, dynamics, and stereo differences.
- Removed the combined similarity score and percentage-style confidence from the P0 report.
- Added textual reliability with explicit `support_count/reference_count` evidence.
- Limited the main screen to three findings; preserved the rest in `additional_findings`.
- Added `technical_details` and explicit measurement-method notes.
- Renamed P95–P10 short-term loudness spread so it is not presented as certified EBU LRA.
- Added dual-mono detection and a diagnostic path for unexpected mono exports.
- Rounded Audiobox PQ to one decimal and removed the invented fixed confidence.
- Added P0 start/verification scripts and regression tests.

## [0.2.0-evidence] — 2026-08-11

### Refactored

- Replaced raw STFT magnitude dB with spectral power shares (%) and centred log-ratios.
- Replaced mean-only genre rules with a three-stage pipeline: measurement → robust comparison → diagnosis.
- Genre no longer determines a hard-coded LUFS target.
- Tonal recommendations now require user references; genre profiles are low-confidence display-only fallback.
- Reference matching now pools 3-second segments and uses median/MAD, per-band confidence and outlier timestamps.
- Reference files skip unused BPM/key extraction to reduce analysis latency.
- Recommendations now include evidence, confidence, timestamps, possible causes and an explicit DAW verification step.
- Removed direct commands such as “cut 21 dB”; broad 0.5–2 dB audition ranges are suggested only after listening confirms a reference delta.

### Added

- BS.1770 K-weighted short-term loudness timeline and EBU Tech 3342-style gated LRA.
- PLR, per-channel true-peak estimates, clipping regions and DC offset.
- Local L/R phase timeline, minimum correlation, mono fold-down RMS delta and Side energy below 150 Hz.
- Key-confidence estimate and explicit uncertainty in the report.
- Optional Audiobox Aesthetics backend pinned to upstream commit `2618e9d`; `PQ` is displayed as an experimental secondary signal.
- Multi-stage DSP Docker image: small deterministic `runtime` and opt-in `audio-ml` target.
- Standalone Docker analysis scripts and JSON CLI.
- Synthetic invariant experiment and nine focused unit tests for the v2 semantics.
- New report UI with metric explanations, spectral percentages, reference confidence and evidence cards.

### Removed from this release

- Demucs dependency, model cache and active stem-analysis path.
- Instrument-specific conclusions from a finished master.
- Uncalibrated “dark/bright”, fixed crest-factor and genre-loudness verdicts.

### Compatibility

- API still accepts the legacy `stem_analysis` field but ignores it, so queued or old clients do not crash.
- Legacy JSON aliases (`lufs`, `true_peak_db`, `band_energy_db`) remain for one transition release.

### Verified

- Python compile check and `git diff --check`.
- 9/9 unit tests passed in a clean environment built from worker requirements.
- Synthetic suite passed: gain invariance, 100% band-share sum, injected sub-bass, local anti-phase, clipping and safe recommendation wording.
- Full Docker/Blazor build remains a host gate because Docker and .NET SDK are unavailable in the handoff environment.

## [0.1.0-mvp] — 2026-08-11

- One-origin Blazor/API deployment, authentication, jobs, reports and history.
- Celery/Redis worker, MinIO transient uploads, PostgreSQL reports and feedback.
- Five genres, up to three references, source cleanup, smoke test and E2E test.
- Fixed missing worker packages and missing frontend JWT flow.
