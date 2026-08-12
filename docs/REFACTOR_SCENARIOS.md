# Refactor scenarios

## Scenario A — Evidence MVP (implemented)

Keep the existing web/API/job architecture and replace the unreliable analysis core.

```text
audio -> deterministic measurements -> robust reference comparison
      -> confidence/evidence rules -> human-readable report
```

Why now: smallest change that fixes the product claim. It removes exact-EQ hallucinations without risking the already working upload/auth/report vertical slice.

## Scenario B — Calibrated diagnosis (next)

Store per-diagnosis feedback (`confirmed`, `false positive`, `artistic intent`) and mix-revision pairs. Estimate precision per rule and calibrate confidence by genre/context. Hide rules that do not reach an agreed precision threshold.

This is more valuable than adding another foundation model because it measures whether SoundDebug helps real producers.

## Scenario C — Semantic context (research)

Add a `MusicContextProvider` interface with MAEST embeddings to:

- detect an implausible selected genre;
- measure whether uploaded references are semantically related;
- cluster references before computing the median profile.

It must not directly generate mastering actions. Run an offline benchmark before including the model in the default image.

## Scenario D — Stem evidence (deferred)

Only after A/B validation, add a separate GPU worker behind `StemSeparator`. Benchmark Demucs/RoFormer candidates on downstream diagnosis stability, bleeding, runtime and VRAM. Separation output must be treated as uncertain derived audio.

## Scenario E — Learned perceptual ranking (optional)

Audiobox PQ is already integrated as an isolated beta. Keep it only if it consistently ranks producer-approved revisions of the same track. Never combine all metrics into one opaque “mix score”.
