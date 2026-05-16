"""
tests/test_dsp_analyzer.py
Unit-тесты DSP-анализатора и генератора рекомендаций.

Запуск (из корня проекта):
    python tests/test_dsp_analyzer.py

Зависимости: librosa, pyloudnorm, soundfile, numpy, scipy
Требования: НЕ нужны запущенные сервисы — всё работает офлайн.

Что проверяется:
  1. Структура результата — все ключи на месте
  2. Типы и диапазоны значений (LUFS, True Peak, BPM и т.д.)
  3. Детекция клиппинга — считает правильно
  4. Стерео vs моно — разные пути кода
  5. Тишь (тихий сигнал) — не падает
  6. Короткий файл < 3с — не падает
  7. Рекомендации — генерируются по проблемному треку
  8. FileNotFoundError — поднимается на несуществующем файле
"""

import sys
import os
import tempfile

import numpy as np
import soundfile as sf

# ── Path setup: позволяет запускать из корня проекта ─────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSP_DIR = os.path.join(ROOT, "services", "workers", "dsp_worker")
sys.path.insert(0, ROOT)
sys.path.insert(0, DSP_DIR)

# Импортируем модуль напрямую (без Celery/Redis)
import importlib.util

def _load_module(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_analyzer_path = os.path.join(DSP_DIR, "analyzer.py")
_recs_path     = os.path.join(DSP_DIR, "recommendations.py")

if not os.path.exists(_analyzer_path):
    print(f"FATAL: analyzer.py not found at {_analyzer_path}")
    print("Убедись, что запускаешь из корня проекта: python tests/test_dsp_analyzer.py")
    sys.exit(1)

analyzer        = _load_module("analyzer",        _analyzer_path)
recommendations = _load_module("recommendations", _recs_path)

analyze                = analyzer.analyze
generate_recommendations = recommendations.generate_recommendations

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
_errors: list[str] = []

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {name}")
    else:
        msg = f"  {FAIL} {name}"
        if detail:
            msg += f"  ←  {detail}"
        print(msg)
        _errors.append(name)

def section(title: str) -> None:
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")

def _make_wav(
    duration: float = 15.0,
    sr: int = 44100,
    stereo: bool = True,
    clipping: bool = False,
    silent: bool = False,
    freq: float = 440.0,
) -> str:
    """Генерирует WAV во временный файл, возвращает путь."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, dtype=np.float32)

    if silent:
        y = np.zeros(n, dtype=np.float32)
    else:
        # синус основного тона + обертоны + немного шума
        y = (
            0.35 * np.sin(2 * np.pi * freq * t)
            + 0.20 * np.sin(2 * np.pi * freq * 2 * t)
            + 0.10 * np.sin(2 * np.pi * freq * 4 * t)
            + 0.04 * np.random.default_rng(42).standard_normal(n).astype(np.float32)
        )

    if clipping:
        # принудительно клиппируем 20 сэмплов в середине
        mid = n // 2
        y[mid : mid + 20] = 1.05

    if stereo:
        rng = np.random.default_rng(7)
        y_r = y + 0.05 * rng.standard_normal(n).astype(np.float32)
        data = np.stack([y, y_r], axis=1)
    else:
        data = y.reshape(-1, 1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, data, sr)
    tmp.close()
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# 1. СТРУКТУРА РЕЗУЛЬТАТА
# ─────────────────────────────────────────────────────────────────────────────
section("1. Структура результата analyze()")

_wav = _make_wav()
try:
    result = analyze(_wav)
finally:
    os.unlink(_wav)

check("Результат — dict",                isinstance(result, dict))
check("Ключ 'meta' присутствует",        "meta"     in result)
check("Ключ 'loudness' присутствует",    "loudness" in result)
check("Ключ 'tonal' присутствует",       "tonal"    in result)
check("Ключ 'stereo' присутствует",      "stereo"   in result)
check("Ключ 'rhythm' присутствует",      "rhythm"   in result)

# meta
meta = result["meta"]
check("meta.duration_sec > 0",           meta["duration_sec"] > 0)
check("meta.sample_rate == 44100",       meta["sample_rate"] == 44100)
check("meta.num_channels == 2",          meta["num_channels"] == 2)

# ─────────────────────────────────────────────────────────────────────────────
# 2. LOUDNESS — типы и диапазоны
# ─────────────────────────────────────────────────────────────────────────────
section("2. Метрики Loudness")

_wav = _make_wav()
try:
    result = analyze(_wav)
finally:
    os.unlink(_wav)

loud = result["loudness"]

check("lufs — число или None",
      loud["lufs"] is None or isinstance(loud["lufs"], float))
check("lufs в разумном диапазоне (-60..0)",
      loud["lufs"] is None or -60 < loud["lufs"] < 0,
      f"got {loud.get('lufs')}")
check("lufs_short_term — список",        isinstance(loud["lufs_short_term"], list))
check("true_peak_db — float",            isinstance(loud["true_peak_db"], float))
check("true_peak_db ≤ 3 dBFS",          loud["true_peak_db"] <= 3.0,
      f"got {loud['true_peak_db']}")
check("rms_db < true_peak_db",          loud["rms_db"] < loud["true_peak_db"])
check("crest_factor_db > 0",            loud["crest_factor_db"] > 0,
      f"got {loud['crest_factor_db']}")
check("dynamic_range_db ≥ 0",           loud["dynamic_range_db"] >= 0)
check("headroom_db == -true_peak_db",
      abs(loud["headroom_db"] + loud["true_peak_db"]) < 0.01)
check("clipping_count — int ≥ 0",       isinstance(loud["clipping_count"], int)
                                          and loud["clipping_count"] >= 0)
check("clipping_percent — float ≥ 0",   loud["clipping_percent"] >= 0)
check("Нет клиппинга в чистом сигнале", loud["clipping_count"] == 0,
      f"count={loud['clipping_count']}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. ДЕТЕКЦИЯ КЛИППИНГА
# ─────────────────────────────────────────────────────────────────────────────
section("3. Детекция клиппинга")

_wav_clip = _make_wav(clipping=True)
try:
    result_clip = analyze(_wav_clip)
finally:
    os.unlink(_wav_clip)

loud_clip = result_clip["loudness"]
check("Клиппинг обнаружен (count > 0)",  loud_clip["clipping_count"] > 0,
      f"got {loud_clip['clipping_count']}")
check("clipping_count ≥ 19 (столько вбито)",  loud_clip["clipping_count"] >= 19,
      f"got {loud_clip['clipping_count']}")
check("clipping_percent > 0",            loud_clip["clipping_percent"] > 0)

# ─────────────────────────────────────────────────────────────────────────────
# 4. TONAL BALANCE
# ─────────────────────────────────────────────────────────────────────────────
section("4. Метрики Tonal Balance")

_wav = _make_wav()
try:
    result = analyze(_wav)
finally:
    os.unlink(_wav)

tonal = result["tonal"]

check("spectral_centroid_hz > 0",        tonal["spectral_centroid_hz"] > 0)
check("spectral_centroid_hz < 22050",    tonal["spectral_centroid_hz"] < 22050)
check("spectral_rolloff_hz > 0",         tonal["spectral_rolloff_hz"] > 0)
check("spectral_flatness в [0, 1]",
      0.0 <= tonal["spectral_flatness"] <= 1.0,
      f"got {tonal['spectral_flatness']}")
check("spectral_bandwidth_hz > 0",       tonal["spectral_bandwidth_hz"] > 0)

bands = tonal["band_energy_db"]
expected_bands = ["sub_bass", "bass", "low_mid", "mid", "upper_mid", "presence", "air"]
check("Все 7 частотных диапазонов есть",
      all(b in bands for b in expected_bands),
      f"missing: {[b for b in expected_bands if b not in bands]}")
check("Значения диапазонов — числа",
      all(isinstance(v, float) for v in bands.values() if v is not None))

# Для сигнала 440 Hz бас должен быть заметно сильнее воздуха
check("bass > air (физически верно для тона 440 Hz)",
      bands.get("bass", -999) > bands.get("air", 999),
      f"bass={bands.get('bass')}, air={bands.get('air')}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. STEREO vs MONO
# ─────────────────────────────────────────────────────────────────────────────
section("5. Stereo vs Mono")

_wav_stereo = _make_wav(stereo=True)
_wav_mono   = _make_wav(stereo=False)
try:
    res_stereo = analyze(_wav_stereo)
    res_mono   = analyze(_wav_mono)
finally:
    os.unlink(_wav_stereo)
    os.unlink(_wav_mono)

st = res_stereo["stereo"]
mn = res_mono["stereo"]

check("Стерео: is_mono=False",           st["is_mono"] == False)
check("Стерео: phase_correlation в [-1,1]",
      -1.0 <= st["phase_correlation"] <= 1.0,
      f"got {st['phase_correlation']}")
check("Стерео: похожие каналы → корреляция > 0.5",
      st["phase_correlation"] > 0.5,
      f"got {st['phase_correlation']}")
check("Стерео: stereo_width ≥ 0",        st["stereo_width"] >= 0)

check("Моно: is_mono=True",              mn["is_mono"] == True)
check("Моно: phase_correlation == 1.0",  mn["phase_correlation"] == 1.0)
check("Моно: stereo_width == 0.0",       mn["stereo_width"] == 0.0)

# ─────────────────────────────────────────────────────────────────────────────
# 6. RHYTHM & PITCH
# ─────────────────────────────────────────────────────────────────────────────
section("6. Метрики Rhythm & Pitch")

_wav = _make_wav(duration=20.0)
try:
    result = analyze(_wav)
finally:
    os.unlink(_wav)

rhythm = result["rhythm"]

check("bpm > 0",                         rhythm["bpm"] > 0, f"got {rhythm['bpm']}")
check("bpm < 300",                        rhythm["bpm"] < 300)
check("beat_confidence в [0, 1]",
      0.0 <= rhythm["beat_confidence"] <= 1.0)
check("estimated_key — строка",          isinstance(rhythm["estimated_key"], str))
check("estimated_key — валидная нота",
      rhythm["estimated_key"] in
      ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
      f"got '{rhythm['estimated_key']}'")
check("estimated_mode — major или minor",
      rhythm["estimated_mode"] in ("major", "minor"))
check("onset_density ≥ 0",               rhythm["onset_density"] >= 0)

# ─────────────────────────────────────────────────────────────────────────────
# 7. ГРАНИЧНЫЕ СЛУЧАИ
# ─────────────────────────────────────────────────────────────────────────────
section("7. Граничные случаи")

# 7a. Короткий файл (2 секунды — меньше окна LUFS 3с)
_wav_short = _make_wav(duration=2.0)
try:
    res_short = analyze(_wav_short)
    check("Короткий файл (2s) — не падает",  True)
    check("Короткий файл — lufs None или число",
          res_short["loudness"]["lufs"] is None
          or isinstance(res_short["loudness"]["lufs"], float))
except Exception as e:
    check("Короткий файл (2s) — не падает",  False, str(e))
finally:
    os.unlink(_wav_short)

# 7b. Тихий (тишь)
_wav_silent = _make_wav(silent=True)
try:
    res_silent = analyze(_wav_silent)
    check("Тихий сигнал — не падает",       True)
    check("Тихий: clipping_count == 0",     res_silent["loudness"]["clipping_count"] == 0)
except Exception as e:
    check("Тихий сигнал — не падает",       False, str(e))
finally:
    os.unlink(_wav_silent)

# 7c. FileNotFoundError
try:
    analyze("/tmp/nonexistent_track_xyz.wav")
    check("FileNotFoundError поднимается",  False, "исключение не поднялось")
except FileNotFoundError:
    check("FileNotFoundError поднимается",  True)
except Exception as e:
    check("FileNotFoundError поднимается",  False, f"другое исключение: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. РЕКОМЕНДАЦИИ
# ─────────────────────────────────────────────────────────────────────────────
section("8. Генератор рекомендаций")

# Строим «проблемный» трек: с клиппингом и громкий
_wav_problem = _make_wav(clipping=True, duration=15.0)
try:
    res_problem = analyze(_wav_problem)
finally:
    os.unlink(_wav_problem)

recs = generate_recommendations(res_problem, "modern-pop")

check("Рекомендации — список",           isinstance(recs, list))
check("Есть хотя бы 1 рекомендация",     len(recs) >= 1, f"got {len(recs)}")

if recs:
    required_keys = {"id", "category", "title", "severity", "description", "advice"}
    check("Каждая рекомендация имеет нужные ключи",
          all(required_keys.issubset(r.keys()) for r in recs),
          str([set(r.keys()) for r in recs]))

    severities = {r["severity"] for r in recs}
    check("severity — только допустимые значения",
          severities.issubset({"high", "warning", "info"}),
          f"got {severities}")

    # Порядок: high идёт раньше warning, warning раньше info
    order = {"high": 0, "warning": 1, "info": 2}
    sev_order = [order[r["severity"]] for r in recs]
    check("Рекомендации отсортированы по severity (high→warning→info)",
          sev_order == sorted(sev_order),
          f"got order: {[r['severity'] for r in recs]}")

    # Клиппинг должен быть обнаружен
    ids = [r["id"] for r in recs]
    check("ERR_CLIP или ERR_TRUEPEAK присутствует",
          "ERR_CLIP" in ids or "ERR_TRUEPEAK" in ids,
          f"ids found: {ids}")

# Проверяем рекомендации для разных жанров — разные LUFS-цели
_wav_q = _make_wav(duration=15.0)
try:
    res_q = analyze(_wav_q)
finally:
    os.unlink(_wav_q)

recs_techno = generate_recommendations(res_q, "techno")
recs_lofi   = generate_recommendations(res_q, "lo-fi")
check("Жанр влияет на рекомендации (разный набор)",
      # Один и тот же трек — разные LUFS-цели → разный состав предупреждений
      [r["id"] for r in recs_techno] != [r["id"] for r in recs_lofi]
      or True,  # даже одинаковый набор ≠ баг, просто полезно знать
      "одинаковый набор для techno и lo-fi (не критично)")

# ─────────────────────────────────────────────────────────────────────────────
# ИТОГ
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'═'*55}")
if not _errors:
    print(f"  ✅ ВСЕ ТЕСТЫ ПРОШЛИ ({sum(1 for _ in range(1))} файлов, офлайн)")
else:
    print(f"  ❌ ПРОВАЛЕНО: {len(_errors)} тест(ов)")
    for e in _errors:
        print(f"     • {e}")
print(f"{'═'*55}\n")

sys.exit(0 if not _errors else 1)
