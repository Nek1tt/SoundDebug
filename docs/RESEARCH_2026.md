# SoundDebug research decisions — 11 August 2026

## Product question

SoundDebug receives a finished master, not a DAW session or clean/reference pair. Therefore the system can reliably measure signal properties, but cannot reliably identify which instrument or processor caused them. The v2 design treats DSP as evidence and uses ML only as an explicitly uncertain additional signal.

## Methods selected for MVP v2

| Method | Status | SoundDebug use | Boundary |
|---|---|---|---|
| [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770) | Implemented | Integrated loudness foundation, K-weighted timeline, per-channel 4× true-peak estimate | Estimate is not a certified meter conformance claim |
| [EBU Tech 3342 v4](https://tech.ebu.ch/publications/tech3342) | Implemented | 3 s short-term distribution, absolute/relative gates, LRA | Short files can return no stable LRA |
| Reference-conditioned spectral comparison | Implemented | Segment pooling, level-independent power ratios, median/MAD, temporal outliers | References express intent; they are not universal truth |
| [Matchering](https://github.com/sergree/matchering) concept | Adapted, not copied | Compare frequency response/loudness/stereo to a user reference | SoundDebug does not process or automatically master audio |
| [Meta Audiobox Aesthetics](https://github.com/facebookresearch/audiobox-aesthetics) | Optional beta | `Production Quality` score as a low-confidence second opinion | No technical diagnosis; subjective/domain-dependent predictor |

Audiobox Aesthetics (2025) decomposes no-reference audio aesthetics into Production Quality, Production Complexity, Content Enjoyment and Content Usefulness. SoundDebug intentionally surfaces only PQ; CE/CU would turn the product into an unsupported judgement of artistic value.

## Relevant SOTA reviewed but not placed in the critical path

### MAEST / Discogs embeddings

[MAEST](https://github.com/palonso/MAEST) is a music-focused transformer representation. [Essentia distributes a 519-style model](https://essentia.upf.edu/models.html) trained on roughly 4M tracks and recommends intermediate-layer embeddings for downstream tasks. It is a strong candidate for semantic reference similarity and checking whether the selected genre is plausible.

It is not a mixing-quality model. Adding it now would make the report look more “AI-powered” without solving the incorrect EQ advice. Planned experiment: compare MAEST cosine distance with expert ratings of reference relevance before enabling it in the UI.

### AudioMOS 2025 and newer generative-audio quality systems

The [AudioMOS Challenge 2025](https://arxiv.org/abs/2509.01336) and follow-up systems evaluate mostly synthetic speech/audio/music. Their progress is relevant to automatic perceptual assessment, but domain transfer to human-produced finished mixes has not been established. Very recent 2026 preprints are research candidates, not dependencies for the 23 August MVP.

### MuQ/MuLan and CLAP-style embeddings

Joint music/text embeddings are useful for retrieval and semantic tags, not for proving clipping, phase cancellation or excessive EQ. Model size/licensing and calibration costs are not justified for the current vertical slice.

### Demucs and RoFormer

Explicitly excluded from v2. Source separation adds model/runtime complexity and separation artefacts. It should return only after the deterministic report is validated, behind a `StemSeparator` interface and a benchmark on downstream diagnosis—not merely SDR.

## Why fixed genre curves are not diagnostic

The v1 JSON curves were hand-authored and had no licensed calibration dataset. A genre label does not specify arrangement, era, mastering destination or artistic intent. V2 keeps them as a low-confidence visual fallback only. They cannot generate tonal recommendations.

## Validation needed after release

1. Collect paired `mix version A/B + producer judgement` examples.
2. Ask users whether each observation was confirmed, false or artistically intentional.
3. Calibrate per-rule precision; hide rules with poor precision.
4. Compare 1, 2 and 3 reference tracks and measure reference-selection sensitivity.
5. Evaluate Audiobox PQ on real mix revisions; disable it if it does not rank revisions consistently.
6. Add MAEST only if semantic similarity improves selection of useful references.
