"""Deterministic, explainable analysis of a finished music mix.

The analyser intentionally reports observations, not mastering decisions.  In
particular, spectral values are energy shares or centred log-ratios.  They are
never interpreted as an EQ gain.  Recommendations are produced later, after a
target/reference comparison has been built.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly, sosfilt

from shared.config import MAX_AUDIO_DURATION_SEC

logger = logging.getLogger(__name__)

CLIP_THRESHOLD = 0.999
EPS = 1e-12
ANALYSIS_WINDOW_SEC = 3.0
ANALYSIS_HOP_SEC = 1.0

FREQ_BANDS: dict[str, tuple[int, int]] = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 6000),
    "presence": (6000, 10000),
    "air": (10000, 20000),
}

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _to_db(amplitude: float | np.floating, eps: float = EPS) -> float:
    return float(20.0 * np.log10(max(float(amplitude), eps)))


def _power_to_db(power: float | np.floating, eps: float = EPS) -> float:
    return float(10.0 * np.log10(max(float(power), eps)))


def _round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _oversampled_peak(channel: np.ndarray, sr: int, factor: int = 4) -> float:
    """Practical per-channel inter-sample peak estimate using 4x resampling."""
    chunk_size = sr * 10
    overlap = 128
    peak = 0.0
    for start in range(0, len(channel), chunk_size):
        left = max(0, start - overlap)
        right = min(len(channel), start + chunk_size + overlap)
        oversampled = resample_poly(channel[left:right], factor, 1)
        peak = max(peak, float(np.max(np.abs(oversampled))))
    return peak


def _load_audio(path: str | Path) -> tuple[np.ndarray, np.ndarray | None, int, int]:
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:
        decoded, sr = librosa.load(str(path), sr=None, mono=False)
        data = decoded[:, np.newaxis] if decoded.ndim == 1 else decoded.T
        data = data.astype(np.float32)

    if data.size == 0 or not np.all(np.isfinite(data)):
        raise ValueError("audio is empty or contains non-finite samples")

    num_channels = int(data.shape[1])
    if num_channels >= 2:
        y_stereo = data[:, :2].T
        y_mono = np.mean(y_stereo, axis=0)
    else:
        y_stereo = None
        y_mono = data[:, 0]
    return y_mono.astype(np.float32), y_stereo, int(sr), num_channels


def _window_starts(length: int, sr: int, window_sec: float, hop_sec: float) -> list[int]:
    window = max(1, int(window_sec * sr))
    hop = max(1, int(hop_sec * sr))
    if length <= window:
        return [0]
    starts = list(range(0, length - window + 1, hop))
    if starts[-1] + window < length:
        starts.append(length - window)
    return starts


def _k_weight(signal: np.ndarray, sr: int) -> np.ndarray:
    """Apply the BS.1770 K-weighting cascade used for loudness time series."""
    # Coefficients follow the De Man implementation used by pyloudnorm.
    def high_shelf() -> tuple[np.ndarray, np.ndarray]:
        gain, q, fc = 4.0, 1.0 / np.sqrt(2.0), 1681.974450955533
        k = np.tan(np.pi * fc / sr)
        vh = 10.0 ** (gain / 20.0)
        vb = vh ** 0.4996667741545416
        a0 = 1.0 + k / q + k * k
        return (
            np.array([(vh + vb * k / q + k * k) / a0,
                      2.0 * (k * k - vh) / a0,
                      (vh - vb * k / q + k * k) / a0]),
            np.array([1.0, 2.0 * (k * k - 1.0) / a0,
                      (1.0 - k / q + k * k) / a0]),
        )

    def high_pass() -> tuple[np.ndarray, np.ndarray]:
        q, fc = 0.5003270373238773, 38.13547087602444
        k = np.tan(np.pi * fc / sr)
        a0 = 1.0 + k / q + k * k
        return (
            np.array([1.0 / a0, -2.0 / a0, 1.0 / a0]),
            np.array([1.0, 2.0 * (k * k - 1.0) / a0,
                      (1.0 - k / q + k * k) / a0]),
        )

    result = np.asarray(signal, dtype=np.float64)
    for b, a in (high_shelf(), high_pass()):
        result = lfilter(b, a, result, axis=0)
    return result


def _loudness_from_power(power: float) -> float:
    return -0.691 + _power_to_db(power)


def _loudness_timeline(signal: np.ndarray, sr: int) -> list[dict[str, float]]:
    weighted = _k_weight(signal, sr)
    if weighted.ndim == 1:
        weighted = weighted[:, np.newaxis]
    result: list[dict[str, float]] = []
    window = int(ANALYSIS_WINDOW_SEC * sr)
    for start in _window_starts(len(weighted), sr, ANALYSIS_WINDOW_SEC, ANALYSIS_HOP_SEC):
        chunk = weighted[start : start + window]
        power = float(np.sum(np.mean(chunk * chunk, axis=0)))
        value = _loudness_from_power(power)
        if np.isfinite(value):
            result.append({"time_sec": round((start + len(chunk) / 2) / sr, 2),
                           "short_term_lufs": round(value, 2)})
    return result


def _short_term_loudness_spread(
    timeline: list[dict[str, float]], integrated_lufs: float | None,
) -> float | None:
    """P95-P10 spread of gated 3 s values; deliberately not labelled EBU LRA."""
    if integrated_lufs is None or len(timeline) < 4:
        return None
    values = np.array([point["short_term_lufs"] for point in timeline], dtype=float)
    gated = values[(values > -70.0) & (values > integrated_lufs - 20.0)]
    if len(gated) < 4:
        return None
    return float(np.percentile(gated, 95) - np.percentile(gated, 10))


def _contiguous_regions(mask: np.ndarray, sr: int, minimum_sec: float = 0.001) -> list[dict[str, float]]:
    padded = np.pad(mask.astype(np.int8), (1, 1))
    edges = np.flatnonzero(np.diff(padded))
    regions: list[dict[str, float]] = []
    for start, end in edges.reshape(-1, 2):
        if (end - start) / sr >= minimum_sec:
            regions.append({"start_sec": round(start / sr, 3), "end_sec": round(end / sr, 3)})
    return regions[:50]


def _loudness_metrics(y_mono: np.ndarray, y_stereo: np.ndarray | None, sr: int) -> dict[str, Any]:
    meter = pyln.Meter(sr)
    signal = y_stereo.T if y_stereo is not None else y_mono
    try:
        integrated = float(meter.integrated_loudness(signal))
        lufs = integrated if np.isfinite(integrated) else None
    except Exception:
        lufs = None

    timeline = _loudness_timeline(signal, sr)
    short_term = [point["short_term_lufs"] for point in timeline]
    channels = y_stereo if y_stereo is not None else y_mono[np.newaxis, :]
    channel_peaks = [_oversampled_peak(channel, sr) for channel in channels]
    true_peak = max(channel_peaks)
    true_peak_db = _to_db(true_peak)

    rms = float(np.sqrt(np.mean(np.square(y_mono, dtype=np.float64))))
    rms_db = _to_db(rms)
    frame_rms = librosa.feature.rms(y=y_mono, frame_length=2048, hop_length=512)[0]
    active_db = 20.0 * np.log10(frame_rms[frame_rms > 1e-7] + EPS)
    dynamic_range = (
        float(np.percentile(active_db, 95) - np.percentile(active_db, 10))
        if len(active_db) >= 10 else None
    )

    clip_mask = np.any(np.abs(channels) >= CLIP_THRESHOLD, axis=0)
    clipping_count = int(np.sum(clip_mask))
    clipping_events = _contiguous_regions(clip_mask, sr)
    dc_by_channel = [float(np.mean(channel)) for channel in channels]

    return {
        "integrated_lufs": _round_or_none(lufs),
        "lufs": _round_or_none(lufs),  # backward-compatible alias
        "loudness_timeline": timeline,
        "lufs_short_term": [round(v, 1) for v in short_term],
        "short_term_min_lufs": _round_or_none(min(short_term) if short_term else None),
        "short_term_max_lufs": _round_or_none(max(short_term) if short_term else None),
        "true_peak_dbtp": round(true_peak_db, 2),
        "true_peak_db": round(true_peak_db, 2),  # backward-compatible alias
        "true_peak_method": "4x-oversampled-per-channel-estimate",
        "true_peak_by_channel_dbtp": [round(_to_db(value), 2) for value in channel_peaks],
        "rms_dbfs": round(rms_db, 2),
        "rms_db": round(rms_db, 2),
        "crest_factor_db": round(true_peak_db - rms_db, 2),
        "plr_lu": _round_or_none(true_peak_db - lufs if lufs is not None else None),
        "dynamic_range_db": _round_or_none(dynamic_range),
        "short_term_loudness_spread_lu": _round_or_none(
            _short_term_loudness_spread(timeline, lufs)
        ),
        "short_term_loudness_spread_method": (
            "P95-P10 of 3-second K-weighted values after absolute/relative gating; not certified EBU LRA"
        ),
        "headroom_db": round(-true_peak_db, 2),
        "clipping_count": clipping_count,
        "clipping_percent": round(100.0 * clipping_count / len(y_mono), 5),
        "clipping_events": clipping_events,
        "dc_offset_by_channel": [round(value, 7) for value in dc_by_channel],
    }


def _band_statistics(power: np.ndarray, freqs: np.ndarray) -> tuple[dict[str, float], dict[str, float]]:
    totals: dict[str, float] = {}
    for name, (low, high) in FREQ_BANDS.items():
        mask = (freqs >= low) & (freqs < min(high, freqs[-1] + 1))
        totals[name] = float(np.sum(power[mask])) if np.any(mask) else 0.0
    total = sum(totals.values()) + EPS
    shares = {name: 100.0 * value / total for name, value in totals.items()}
    log_shares = {name: _power_to_db(value / total) for name, value in totals.items()}
    centre = float(np.median(list(log_shares.values())))
    balance = {name: value - centre for name, value in log_shares.items()}
    return shares, balance


def _tonal_metrics(y_mono: np.ndarray, sr: int) -> dict[str, Any]:
    n_fft = 4096
    hop = 1024
    spectrum = np.abs(librosa.stft(y_mono, n_fft=n_fft, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    mean_power = np.mean(spectrum, axis=1)
    shares, balance = _band_statistics(mean_power, freqs)

    centroid = librosa.feature.spectral_centroid(S=np.sqrt(spectrum), sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(S=np.sqrt(spectrum), sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(S=np.sqrt(spectrum))[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=np.sqrt(spectrum), sr=sr)[0]

    segment_frames = max(1, int(ANALYSIS_WINDOW_SEC * sr / hop))
    segment_hop = max(1, int(ANALYSIS_HOP_SEC * sr / hop))
    timeline: list[dict[str, Any]] = []
    for frame in range(0, max(1, spectrum.shape[1] - segment_frames + 1), segment_hop):
        chunk = spectrum[:, frame : frame + segment_frames]
        if chunk.size == 0:
            continue
        chunk_shares, chunk_balance = _band_statistics(np.mean(chunk, axis=1), freqs)
        timeline.append({
            "time_sec": round((frame + chunk.shape[1] / 2) * hop / sr, 2),
            "band_energy_pct": {key: round(value, 3) for key, value in chunk_shares.items()},
            "band_balance_db": {key: round(value, 2) for key, value in chunk_balance.items()},
        })

    return {
        "spectral_centroid_hz": round(float(np.median(centroid)), 1),
        "spectral_rolloff_hz": round(float(np.median(rolloff)), 1),
        "spectral_flatness": round(float(np.median(flatness)), 4),
        "spectral_bandwidth_hz": round(float(np.median(bandwidth)), 1),
        "band_energy_pct": {key: round(value, 3) for key, value in shares.items()},
        "band_balance_db": {key: round(value, 2) for key, value in balance.items()},
        # Compatibility alias.  Unlike v1 these are centred log-ratios, not raw
        # magnitude dB, and the UI labels the representation explicitly.
        "band_energy_db": {key: round(value, 2) for key, value in balance.items()},
        "tonal_timeline": timeline,
        "representation": "power-share-and-centred-log-ratio-v2",
    }


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    if np.std(left) < EPS or np.std(right) < EPS:
        return 1.0 if np.allclose(left, right) else 0.0
    return float(np.clip(np.corrcoef(left, right)[0, 1], -1.0, 1.0))


def _stereo_metrics(y_mono: np.ndarray, y_stereo: np.ndarray | None, sr: int) -> dict[str, Any]:
    if y_stereo is None:
        return {
            "stereo_width": 0.0,
            "phase_correlation": 1.0,
            "minimum_phase_correlation": 1.0,
            "mono_fold_down_loss_db": 0.0,
            "bass_side_energy_pct": 0.0,
            "phase_risk_segments": [],
            "is_mono": True,
            "channel_layout": "mono",
        }

    left, right = y_stereo[0], y_stereo[1]
    mid = (left + right) / 2.0
    side = (left - right) / 2.0
    mid_rms = float(np.sqrt(np.mean(mid * mid)))
    side_rms = float(np.sqrt(np.mean(side * side)))
    stereo_rms = float(np.sqrt(np.mean((left * left + right * right) / 2.0)))
    mono_loss = _to_db(mid_rms / (stereo_rms + EPS))

    cutoff = min(150.0, sr * 0.45)
    sos = butter(4, cutoff, btype="lowpass", fs=sr, output="sos")
    low_mid = sosfilt(sos, mid)
    low_side = sosfilt(sos, side)
    bass_side_pct = 100.0 * float(np.sum(low_side * low_side)) / (
        float(np.sum(low_mid * low_mid) + np.sum(low_side * low_side)) + EPS
    )

    window = int(ANALYSIS_WINDOW_SEC * sr)
    phase_timeline: list[dict[str, float]] = []
    for start in _window_starts(len(left), sr, ANALYSIS_WINDOW_SEC, ANALYSIS_HOP_SEC):
        end = min(len(left), start + window)
        corr = _safe_corr(left[start:end], right[start:end])
        phase_timeline.append({"time_sec": round((start + end) / 2 / sr, 2),
                               "correlation": round(corr, 4)})
    risky = [point for point in phase_timeline if point["correlation"] < 0.0]

    effectively_mono = side_rms / (mid_rms + EPS) < 0.001
    return {
        "stereo_width": round(side_rms / (mid_rms + EPS), 4),
        "phase_correlation": round(_safe_corr(left, right), 4),
        "minimum_phase_correlation": round(min(p["correlation"] for p in phase_timeline), 4),
        "mono_fold_down_loss_db": round(mono_loss, 2),
        "bass_side_energy_pct": round(bass_side_pct, 2),
        "phase_timeline": phase_timeline,
        "phase_risk_segments": risky[:20],
        "is_mono": effectively_mono,
        "channel_layout": "dual-mono" if effectively_mono else "stereo",
    }


def _rhythm_pitch_metrics(y_mono: np.ndarray, sr: int) -> dict[str, Any]:
    onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr)
    tempo_arr, beats = librosa.beat.beat_track(y=y_mono, sr=sr, onset_envelope=onset_env)
    bpm = float(np.atleast_1d(tempo_arr)[0])
    beat_strength = onset_env[beats] if len(beats) else np.array([])
    confidence = (
        float(np.median(beat_strength) / (np.percentile(onset_env, 95) + EPS))
        if len(beat_strength) else 0.0
    )

    chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    key_idx = int(np.argmax(chroma_mean))
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    best: tuple[float, int, str] = (-2.0, 0, "major")
    for root in range(12):
        for mode, profile in (("major", major_profile), ("minor", minor_profile)):
            score = float(np.corrcoef(chroma_mean, np.roll(profile, root))[0, 1])
            if score > best[0]:
                best = (score, root, mode)

    duration_sec = len(y_mono) / sr
    onsets = librosa.onset.onset_detect(y=y_mono, sr=sr, onset_envelope=onset_env)
    return {
        "bpm": round(bpm, 1),
        "beat_confidence": round(float(np.clip(confidence, 0.0, 1.0)), 3),
        "estimated_key": KEYS[best[1]],
        "estimated_mode": best[2],
        "key_confidence": round(float(np.clip((best[0] + 1.0) / 2.0, 0.0, 1.0)), 3),
        "onset_density": round(len(onsets) / max(duration_sec, 1.0), 2),
    }


def analyze(path: str | Path, *, include_rhythm: bool = True) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    try:
        y_mono, y_stereo, sr, num_channels = _load_audio(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load audio: {exc}") from exc

    duration_sec = len(y_mono) / sr
    if duration_sec > MAX_AUDIO_DURATION_SEC:
        raise RuntimeError(f"Audio is {duration_sec:.1f}s; MVP limit is {MAX_AUDIO_DURATION_SEC}s")
    if duration_sec < 0.25:
        raise RuntimeError("Audio is too short; at least 0.25 seconds is required")

    try:
        loudness = _loudness_metrics(y_mono, y_stereo, sr)
        tonal = _tonal_metrics(y_mono, sr)
        stereo = _stereo_metrics(y_mono, y_stereo, sr)
        rhythm = _rhythm_pitch_metrics(y_mono, sr) if include_rhythm else {}
    except Exception as exc:
        raise RuntimeError(f"DSP computation failed: {exc}") from exc

    result: dict[str, Any] = {
        "meta": {
            "duration_sec": round(duration_sec, 2),
            "sample_rate": sr,
            "num_channels": num_channels,
            "analysis_version": "dsp-v2",
        },
        "loudness": loudness,
        "tonal": tonal,
        "stereo": stereo,
        "rhythm": rhythm,
    }
    logger.info("[DSP] Done: %s | LUFS=%s | BPM=%s", path.name, loudness["lufs"], rhythm.get("bpm"))
    return result
