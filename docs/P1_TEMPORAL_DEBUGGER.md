# P1 — Temporal Audio Debugger

Baseline: `release/mvp` commit `c021832ad8455ff3f07121d72bd596912eb1f1fe` (`P0 point of roadmap`).

## Purpose

P1 localises evidence without pretending to recognise musical sections or know a correct mastering decision. Its output answers `where to listen and why`.

## Window contract

- Window length: 6.0 seconds.
- Hop: 1.5 seconds.
- All metrics share the same start/end timestamps.
- The final short window is aligned to the end of the file.
- A derived 240-bin waveform envelope is stored for display; source audio is not stored in the report.

Each window contains loudness, RMS, crest factor, P90–P10 active-frame dynamics spread, transient density, spectral centroid, rolloff, flatness, bandwidth, seven power shares and centred log-ratio tonal bands, Mid/Side share, stereo width, L/R correlation, mono fold-down loss, and Side energy below 150 Hz.

## Detection

Local evidence compares a window with robust surrounding-window median/MAD. Reference evidence compares the target value against each reference track's own temporal median and robust dispersion. A reference is one vote regardless of how many windows it contains.

Absolute phase/mono risks can also trigger evidence. Detection thresholds are intentionally conservative and are not quality boundaries.

## Merge and ranking

Overlapping or immediately adjacent candidate windows of the same category are merged. One region therefore represents one episode instead of repeated warnings for every overlapping window.

Ranking contains explicit components:

- normalized magnitude;
- duration;
- number of confirming metrics;
- reference stability.

The combined score orders regions only. It is not a song-quality score or calibrated probability.

At most 12 public regions are retained so every timeline marker has a corresponding diagnostic card. A nearest comparison window is attached only when it does not overlap the anomalous region.

## Report and frontend

`temporal_analysis.windows` contains timestamped raw feature vectors. `temporal_analysis.regions` contains merged evidence, ranking components, reference support, and `finding_id`.

Clicking a timeline marker selects and immediately renders its card. Every temporal card adds `Где слушать`, followed by the normal P0 blocks: measurements, reasoning, audible interpretation, possible causes, DAW checks, automation warning, and reference context.

## Boundaries

- No verse/chorus/drop recognition.
- No time alignment between target and references.
- No inference of the offending instrument from a stereo master.
- No conversion from temporal/reference delta to plugin settings.
- No claim that an anomaly is necessarily undesirable; an arrangement change may be intentional.
