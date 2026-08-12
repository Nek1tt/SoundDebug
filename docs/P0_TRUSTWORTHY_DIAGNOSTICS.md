# P0 — Trustworthy Diagnostic Engine

## Delivered contract

P0 separates three kinds of statements:

- `FACT` — a directly measured state such as sample clipping, the channel layout, DC offset, or a true-peak estimate with its method stated.
- `REFERENCE_DIFFERENCE` — a difference from user-selected tracks. It is never called an error.
- `HYPOTHESIS` — an interpretation that must be checked by listening or inside the DAW.

Every diagnostic card contains: priority, what was detected, why it was selected, what it may mean audibly, multiple possible causes, an ordered DAW check, an explicit warning against automatic correction, evidence, reliability, timestamps when available, and reference context when references were used.

The main report contains no more than three priority cards. Remaining conclusions are preserved in `additional_findings`; unprocessed measurements and method notes are in `technical_details`.

## Reference comparison

Each reference track is one independent vote. Segments within the same track are used only for temporal localisation and cannot inflate agreement.

The comparison stores independent domains:

- `loudness_difference` — integrated loudness difference and per-reference values;
- `tonal_shape_difference` — gain-invariant relative spectral shape;
- `dynamics_difference` — PLR, P95–P10 short-term spread, and crest factor;
- `stereo_difference` — width, correlation, mono fold-down, and low-band Side energy.

Every domain records the median, MAD, per-reference differences, support count, reference count, and a textual reliability explanation. There is no combined similarity score and no percentage called confidence.

## Interpretation rules

- Genre curves are context only and do not create recommendations.
- The P95–P10 short-term indicator is not called EBU LRA.
- The 4× true-peak estimate is labelled as an estimate.
- A reference delta is never copied to EQ gain, compressor threshold, ratio, attack, release, or Q.
- Audiobox PQ remains optional, is rounded to one decimal, and has no invented confidence.
- Stereo masters cannot identify the exact instrument or processing stage that caused a difference.

## Run

Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/start-p0.ps1
./scripts/smoke-test.ps1
```

Linux/macOS:

```bash
chmod +x scripts/*.sh
./scripts/start-p0.sh
./scripts/smoke-test.sh
```

Local report with references:

```powershell
./scripts/analyze.ps1 -Track "C:\Music\mix.wav" -Genre techno `
  -Reference "C:\Music\ref-1.wav","C:\Music\ref-2.wav","C:\Music\ref-3.wav"
```

The report is written to `analysis-output/report.json`.

## Verify

```powershell
./scripts/verify-p0.ps1
```

or:

```bash
./scripts/verify-p0.sh
```

The full host gate includes Python unit tests, Compose validation, a Release frontend build, stack smoke test, and analysis of real target/reference files.
