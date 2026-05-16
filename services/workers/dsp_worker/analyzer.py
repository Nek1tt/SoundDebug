"""
services/workers/dsp_worker/analyzer.py

DSP-анализатор аудиофайла.
Принимает путь к файлу (.wav / .mp3), возвращает словарь метрик.

МЕТРИКИ:
  Loudness & Dynamics
    lufs              — интегральная громкость (EBU R128), дБ
    lufs_short_term   — список короткосрочных значений LUFS (3с окна)
    true_peak_db      — максимальный пик сигнала, дБFS
    rms_db            — средний RMS по треку, дБFS
    crest_factor_db   — пик/RMS, показывает «сжатость» динамики
    dynamic_range_db  — разброс громкости P95–P10 по фреймам
    headroom_db       — запас до 0 dBFS (=-true_peak)
    clipping_count    — число сэмплов превысивших 0.99 (клиппинг)
    clipping_percent  — то же в процентах

  Tonal Balance
    spectral_centroid_hz   — «центр тяжести» спектра (яркость)
    spectral_rolloff_hz    — частота, ниже которой 85% энергии
    spectral_flatness      — 0=тональный, 1=шумовой сигнал
    spectral_bandwidth_hz  — ширина спектра
    band_energy_db         — энергия по 7 диапазонам:
                             sub_bass / bass / low_mid / mid /
                             upper_mid / presence / air

  Stereo & Phase
    stereo_width      — отношение S/M (side/mid), 0=моно
    phase_correlation — корреляция L/R (-1..1), <0.5 = проблемы

  Rhythm & Pitch
    bpm               — темп
    beat_confidence   — уверенность beat-трекера (0..1)
    estimated_key     — тональность (C, C#, D, …)
    onset_density     — плотность транзиентов (атак/сек)

  Meta
    duration_sec      — длина трека
    sample_rate       — частота дискретизации
    num_channels      — 1=моно / 2=стерео
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf

logger = logging.getLogger(__name__)

# ── Константы ────────────────────────────────────────────────────────────────

CLIP_THRESHOLD = 0.99  # амплитуда ≥ этого = клиппинг

# Частотные диапазоны (Hz): имена → (low, high)
FREQ_BANDS: dict[str, tuple[int, int]] = {
    "sub_bass":   (20,    60),
    "bass":       (60,   250),
    "low_mid":    (250,  500),
    "mid":        (500,  2000),
    "upper_mid":  (2000, 6000),
    "presence":   (6000, 10000),
    "air":        (10000, 20000),
}

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_db(amplitude: float | np.floating, eps: float = 1e-9) -> float:
    return float(20 * np.log10(float(amplitude) + eps))


def _load_audio(path: str | Path) -> tuple[np.ndarray, np.ndarray | None, int, int]:
    """
    Загружает аудио.
    Возвращает (y_mono, y_stereo_or_None, sr, num_channels).
    y_mono  — float32 моно, нормированный в [-1, 1]
    y_stereo — (2, N) если исходный файл стерео, иначе None
    """
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    num_channels = data.shape[1]

    # Нормировка, чтобы не было тихих треков со сдвинутым DC
    if data.max() > 1.0:
        data = data / 32768.0  # 16-bit int → float

    if num_channels >= 2:
        y_stereo = data[:, :2].T  # (2, N)
        y_mono = (y_stereo[0] + y_stereo[1]) / 2.0
    else:
        y_stereo = None
        y_mono = data[:, 0]

    # librosa ожидает float32
    y_mono = y_mono.astype(np.float32)
    return y_mono, y_stereo, sr, num_channels


# ── Группы метрик ────────────────────────────────────────────────────────────

def _loudness_metrics(y_mono: np.ndarray, y_stereo: np.ndarray | None, sr: int) -> dict[str, Any]:
    """EBU R128 LUFS, True Peak, RMS, Crest Factor, Dynamic Range, Clipping."""
    meter = pyln.Meter(sr)

    # pyloudnorm принимает (N,) или (N, channels)
    if y_stereo is not None:
        signal_for_lufs = y_stereo.T  # (N, 2)
    else:
        signal_for_lufs = y_mono

    try:
        lufs = float(meter.integrated_loudness(signal_for_lufs))
    except Exception:
        # Трек слишком короткий — fallback
        lufs = float("nan")

    # Short-term LUFS (каждые ~3 секунды)
    block = sr * 3
    short_term_list: list[float] = []
    for i in range(0, len(y_mono) - block, block):
        chunk = y_mono[i : i + block]
        try:
            st = float(meter.integrated_loudness(chunk))
            if np.isfinite(st):
                short_term_list.append(round(st, 1))
        except Exception:
            pass

    true_peak = float(np.max(np.abs(y_mono)))
    true_peak_db = _to_db(true_peak)

    rms = float(np.sqrt(np.mean(y_mono**2)))
    rms_db = _to_db(rms)

    crest_factor_db = true_peak_db - rms_db

    frame_rms = librosa.feature.rms(y=y_mono, frame_length=2048, hop_length=512)[0]
    frame_rms_db = 20 * np.log10(frame_rms + 1e-9)
    dynamic_range_db = float(np.percentile(frame_rms_db, 95) - np.percentile(frame_rms_db, 10))

    headroom_db = -true_peak_db

    clip_mask = np.abs(y_mono) >= CLIP_THRESHOLD
    clipping_count = int(np.sum(clip_mask))
    clipping_percent = round(100.0 * clipping_count / len(y_mono), 4)

    return {
        "lufs": round(lufs, 2) if np.isfinite(lufs) else None,
        "lufs_short_term": short_term_list,
        "true_peak_db": round(true_peak_db, 2),
        "rms_db": round(rms_db, 2),
        "crest_factor_db": round(crest_factor_db, 2),
        "dynamic_range_db": round(dynamic_range_db, 2),
        "headroom_db": round(headroom_db, 2),
        "clipping_count": clipping_count,
        "clipping_percent": clipping_percent,
    }


def _tonal_metrics(y_mono: np.ndarray, sr: int) -> dict[str, Any]:
    """Спектральные метрики + частотный баланс по диапазонам."""
    centroid = librosa.feature.spectral_centroid(y=y_mono, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y_mono, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(y=y_mono)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y_mono, sr=sr)[0]

    # Частотный баланс
    S = np.abs(librosa.stft(y_mono, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

    band_energy: dict[str, float] = {}
    for name, (flo, fhi) in FREQ_BANDS.items():
        mask = (freqs >= flo) & (freqs < fhi)
        if mask.any():
            energy = float(np.mean(S[mask, :]))
            band_energy[name] = round(_to_db(energy), 2)
        else:
            band_energy[name] = None  # type: ignore[assignment]

    return {
        "spectral_centroid_hz": round(float(np.mean(centroid)), 1),
        "spectral_rolloff_hz": round(float(np.mean(rolloff)), 1),
        "spectral_flatness": round(float(np.mean(flatness)), 4),
        "spectral_bandwidth_hz": round(float(np.mean(bandwidth)), 1),
        "band_energy_db": band_energy,
    }


def _stereo_metrics(y_mono: np.ndarray, y_stereo: np.ndarray | None) -> dict[str, Any]:
    """Стерео ширина и фазовая корреляция. Для моно — фиксированные значения."""
    if y_stereo is None:
        return {
            "stereo_width": 0.0,
            "phase_correlation": 1.0,
            "is_mono": True,
        }

    L, R = y_stereo[0], y_stereo[1]

    # Корреляция Пирсона L/R
    corr_matrix = np.corrcoef(L, R)
    phase_correlation = round(float(corr_matrix[0, 1]), 4)

    # M/S ширина
    mid = (L + R) / 2.0
    side = (L - R) / 2.0
    mid_rms = float(np.sqrt(np.mean(mid**2)))
    side_rms = float(np.sqrt(np.mean(side**2)))
    stereo_width = round(side_rms / (mid_rms + 1e-9), 4)

    return {
        "stereo_width": stereo_width,
        "phase_correlation": phase_correlation,
        "is_mono": False,
    }


def _rhythm_pitch_metrics(y_mono: np.ndarray, sr: int) -> dict[str, Any]:
    """BPM, тональность, плотность транзиентов."""
    # BPM
    tempo_arr, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
    bpm = round(float(np.atleast_1d(tempo_arr)[0]), 1)

    # Beat confidence через onset strength
    onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr)
    beat_confidence = round(float(np.mean(onset_env) / (np.max(onset_env) + 1e-9)), 4)

    # Тональность (хроматограмма)
    chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    key_idx = int(np.argmax(chroma_mean))
    estimated_key = KEYS[key_idx]

    # Мажор / минор: сравниваем профили Кращмара
    # Упрощённый вариант: сдвинутая хроматограмма
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                               2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                               2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    rolled = np.roll(chroma_mean, -key_idx)
    major_score = float(np.corrcoef(rolled, major_profile)[0, 1])
    minor_score = float(np.corrcoef(rolled, minor_profile)[0, 1])
    mode = "major" if major_score >= minor_score else "minor"

    # Плотность транзиентов
    duration_sec = len(y_mono) / sr
    onsets = librosa.onset.onset_detect(y=y_mono, sr=sr)
    onset_density = round(len(onsets) / max(duration_sec, 1.0), 2)

    return {
        "bpm": bpm,
        "beat_confidence": beat_confidence,
        "estimated_key": estimated_key,
        "estimated_mode": mode,
        "onset_density": onset_density,
    }


# ── Публичный API ─────────────────────────────────────────────────────────────

def analyze(path: str | Path) -> dict[str, Any]:
    """
    Главная функция. Принимает путь к .wav/.mp3, возвращает полный
    словарь метрик, готовый к сериализации в JSON.

    Raises:
        FileNotFoundError: файл не существует
        RuntimeError: ошибка при анализе (corrupt file и т.д.)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    logger.info(f"[DSP] Analyzing: {path.name}")

    try:
        y_mono, y_stereo, sr, num_channels = _load_audio(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load audio: {exc}") from exc

    duration_sec = round(len(y_mono) / sr, 2)

    try:
        loudness = _loudness_metrics(y_mono, y_stereo, sr)
        tonal = _tonal_metrics(y_mono, sr)
        stereo = _stereo_metrics(y_mono, y_stereo)
        rhythm = _rhythm_pitch_metrics(y_mono, sr)
    except Exception as exc:
        raise RuntimeError(f"DSP computation failed: {exc}") from exc

    result: dict[str, Any] = {
        "meta": {
            "duration_sec": duration_sec,
            "sample_rate": sr,
            "num_channels": num_channels,
        },
        "loudness": loudness,
        "tonal": tonal,
        "stereo": stereo,
        "rhythm": rhythm,
    }

    logger.info(f"[DSP] Done: {path.name} | LUFS={loudness['lufs']} | BPM={rhythm['bpm']}")
    return result
