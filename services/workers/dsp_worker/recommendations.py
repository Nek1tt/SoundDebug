"""
services/workers/dsp_worker/recommendations.py

Движок диагностики: превращает сырые метрики DSP
в список образовательных рекомендаций.

Каждая рекомендация — словарь:
    {
        "id":          "ERR_01",           # уникальный код
        "category":    "technical",        # technical | tonal_balance | stereo | dynamics
        "title":       "Клиппинг сигнала", # заголовок
        "severity":    "high",             # high | warning | info
        "description": "...",              # объяснение проблемы
        "advice":      "...",              # конкретное действие
        "value":       -6.2,              # измеренное значение (для UI)
        "unit":        "LUFS",            # единица измерения
        "target":      -14.0,            # эталонное значение (если есть)
    }
"""

from __future__ import annotations

from typing import Any

# ── Отраслевые пороги ─────────────────────────────────────────────────────────

# Целевые LUFS по жанрам (интегральная громкость для стриминга)
GENRE_LUFS_TARGET: dict[str, float] = {
    "lo-fi":       -16.0,
    "modern-pop":  -14.0,
    "hip-hop":     -12.0,
    "techno":      -9.0,   # Techno традиционно громче
    "electronic":  -11.0,
}
GENRE_LUFS_TOLERANCE = 3.0  # ±3 LUFS — нормальное отклонение

# Crest Factor: ниже 6 дБ → слишком сжатый («перекомпрессированный»)
CREST_FACTOR_MIN = 6.0
# Динамический диапазон
DYNAMIC_RANGE_MIN = 3.0  # dB, ниже — кирпич

# True Peak: стандарт стриминга -1.0 dBFS (Apple -1, Spotify -1, YouTube -1)
TRUE_PEAK_LIMIT = -1.0

# Стерео
PHASE_CORR_MIN = 0.4       # ниже → подозрение на противофазу
STEREO_WIDTH_MAX = 1.5     # очень широкий → возможны проблемы в моно

# Тональный баланс: отклонение от «нормального» диапазона (dB)
BAND_EXCESS_THRESHOLD = 6.0   # на столько выше соседних диапазонов = проблема

# BPM
BPM_MIN, BPM_MAX = 50.0, 200.0  # вне диапазона = ошибка трекера

# ── Вспомогательные функции ───────────────────────────────────────────────────

def _rec(
    code: str,
    category: str,
    title: str,
    severity: str,
    description: str,
    advice: str,
    value: Any = None,
    unit: str = "",
    target: Any = None,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "id": code,
        "category": category,
        "title": title,
        "severity": severity,
        "description": description,
        "advice": advice,
    }
    if value is not None:
        r["value"] = value
    if unit:
        r["unit"] = unit
    if target is not None:
        r["target"] = target
    return r


# ── Детекторы проблем ──────────────────────────────────────────────────────────

def _check_clipping(loudness: dict) -> list[dict]:
    recs = []
    count = loudness.get("clipping_count", 0)
    pct = loudness.get("clipping_percent", 0.0)
    if count > 0:
        severity = "high" if pct > 0.1 else "warning"
        recs.append(_rec(
            "ERR_CLIP",
            "technical",
            "Клиппинг (цифровое искажение)",
            severity,
            f"Обнаружено {count} сэмплов с амплитудой ≥ 0.99 ({pct:.3f}% трека). "
            "Клиппинг — это цифровое обрезание сигнала: когда волна «упирается» в потолок 0 dBFS, "
            "появляются жёсткие прямоугольные искажения, неотличимые от дешёвого перегруза.",
            "Убавьте мастер-фейдер на 1.5–3 dB. Если громкость важна — вместо фейдера "
            "используйте True Peak Limiter (например, FabFilter Pro-L 2) с порогом -1.0 dBTP.",
            value=count,
            unit="samples",
        ))
    return recs


def _check_true_peak(loudness: dict) -> list[dict]:
    recs = []
    tp = loudness.get("true_peak_db")
    if tp is None:
        return recs
    if tp > TRUE_PEAK_LIMIT:
        recs.append(_rec(
            "ERR_TRUEPEAK",
            "technical",
            "True Peak превышает норму стриминга",
            "high",
            f"True Peak = {tp:.2f} dBFS, норма для Spotify / Apple Music / YouTube = {TRUE_PEAK_LIMIT} dBFS. "
            "При конвертации в сжатые форматы (AAC, MP3) возникают inter-sample peaks — "
            "невидимые пики между сэмплами, которые вызывают искажения у слушателя.",
            "Поставьте True Peak Limiter на мастер-шине с потолком -1.0 dBTP. "
            "Проверьте результат в любом EBU R128-анализаторе (Youlean, SPAN).",
            value=tp,
            unit="dBTP",
            target=TRUE_PEAK_LIMIT,
        ))
    elif tp > -0.3:
        recs.append(_rec(
            "WARN_HEADROOM",
            "technical",
            "Почти нет запаса (headroom)",
            "warning",
            f"True Peak = {tp:.2f} dBFS. Очень мало headroom. "
            "После мастеринга и конвертации сигнал может перегрузиться.",
            "Рекомендуется держать True Peak не выше -1.0 dBFS перед сдачей на стриминг.",
            value=tp,
            unit="dBTP",
        ))
    return recs


def _check_lufs(loudness: dict, genre: str) -> list[dict]:
    recs = []
    lufs = loudness.get("lufs")
    if lufs is None:
        return recs
    target = GENRE_LUFS_TARGET.get(genre, -14.0)
    diff = lufs - target

    if diff > GENRE_LUFS_TOLERANCE:
        recs.append(_rec(
            "WARN_OVERLOUD",
            "dynamics",
            "Трек слишком громкий для жанра",
            "warning",
            f"LUFS = {lufs:.1f}, целевое для {genre} = {target:.0f} LUFS. "
            "Стриминговые сервисы нормализуют громкость: слишком громкий трек "
            "будет тихонько убавлен, что сделает ваш мастеринг бессмысленным.",
            f"Убавьте общую громкость до {target:.0f} LUFS. "
            "Если хотите громко — используйте динамику (Crest Factor), а не просто уровень.",
            value=round(lufs, 1),
            unit="LUFS",
            target=target,
        ))
    elif diff < -GENRE_LUFS_TOLERANCE:
        recs.append(_rec(
            "WARN_QUIET",
            "dynamics",
            "Трек тише нормы для жанра",
            "warning",
            f"LUFS = {lufs:.1f}, целевое для {genre} = {target:.0f} LUFS. "
            "Трек будет звучать тихо на фоне конкурентов в плейлисте.",
            f"Подтяните мастер до {target:.0f} LUFS. Работайте с компрессией и лимитингом, "
            "не просто поднимайте фейдер — это вызовет клиппинг.",
            value=round(lufs, 1),
            unit="LUFS",
            target=target,
        ))
    return recs


def _check_dynamics(loudness: dict) -> list[dict]:
    recs = []
    crest = loudness.get("crest_factor_db", 99.0)
    dr = loudness.get("dynamic_range_db", 99.0)

    if crest < CREST_FACTOR_MIN:
        recs.append(_rec(
            "WARN_OVERCOMPRESSED",
            "dynamics",
            "Перекомпрессия — потеря динамики",
            "warning",
            f"Crest Factor = {crest:.1f} dB (норма ≥ {CREST_FACTOR_MIN} dB). "
            "Слишком мало разницы между тихими и громкими моментами. "
            "Это типичный признак «loudness war» — трек звучит устало и плоско.",
            "Уменьшите ratio или attack на мастер-компрессоре. "
            "Попробуйте параллельную компрессию вместо прямой. "
            "Цель: Crest Factor 8–15 dB для большинства жанров.",
            value=round(crest, 1),
            unit="dB",
            target=CREST_FACTOR_MIN,
        ))

    if dr < DYNAMIC_RANGE_MIN:
        recs.append(_rec(
            "INFO_BRICK",
            "dynamics",
            "Очень малый динамический диапазон",
            "info",
            f"Dynamic Range = {dr:.1f} dB. Трек звучит одинаково громко на протяжении всего времени. "
            "Это не всегда плохо (электронная музыка часто намеренно плоская), "
            "но может сделать трек утомительным при долгом прослушивании.",
            "Добавьте динамические моменты: вступление тише, дроп громче. "
            "Используйте автоматизацию громкости и фильтров.",
            value=round(dr, 1),
            unit="dB",
        ))
    return recs


def _check_stereo(stereo: dict) -> list[dict]:
    recs = []
    corr = stereo.get("phase_correlation", 1.0)
    width = stereo.get("stereo_width", 0.0)
    is_mono = stereo.get("is_mono", True)

    if is_mono:
        recs.append(_rec(
            "INFO_MONO",
            "stereo",
            "Моно-файл",
            "info",
            "Загружен моно-трек. Метрики стерео недоступны.",
            "Если это готовый мастер — убедитесь, что ваш DAW рендерит стерео. "
            "Для большинства стриминговых платформ нужен стерео-файл.",
        ))
        return recs

    if corr < PHASE_CORR_MIN:
        recs.append(_rec(
            "ERR_PHASE",
            "stereo",
            "Проблема с фазой — возможная противофаза",
            "high",
            f"Phase Correlation = {corr:.3f} (норма ≥ {PHASE_CORR_MIN}). "
            "Когда L и R каналы находятся в противофазе, при воспроизведении в моно "
            "(Bluetooth-колонка, телефон) часть звука исчезнет или инвертируется. "
            "Проверьте бас — именно там чаще всего возникает проблема.",
            "Включите «Mono» на мастер-шине и прослушайте. "
            "Инструмент с фазовой проблемой исчезнет или изменится. "
            "Используйте плагин Correlation Meter (iZotope Insight, SPAN Plus) "
            "и Mono Maker для баса ниже 150 Hz.",
            value=round(corr, 3),
            target=PHASE_CORR_MIN,
        ))
    elif corr < 0.7:
        recs.append(_rec(
            "WARN_PHASE",
            "stereo",
            "Слабая моно-совместимость",
            "warning",
            f"Phase Correlation = {corr:.3f}. Стерео широкое, но может возникнуть "
            "потеря низких частот при прослушивании в моно.",
            "Используйте Mid/Side EQ: убедитесь, что бас (<120 Hz) сосредоточен в Mid-канале.",
            value=round(corr, 3),
        ))

    if width > STEREO_WIDTH_MAX:
        recs.append(_rec(
            "WARN_OVERWIDE",
            "stereo",
            "Чрезмерное расширение стерео",
            "warning",
            f"Stereo Width = {width:.2f} (рекомендуется < {STEREO_WIDTH_MAX}). "
            "Сильно расширенное стерео часто содержит фазовые проблемы и звучит «дырявым» в центре.",
            "Снизьте усиление стерео-расширителя. "
            "Следите за балансом Mid/Side: Mid должен оставаться плотным.",
            value=round(width, 2),
            target=STEREO_WIDTH_MAX,
        ))
    return recs


def _check_tonal_balance(tonal: dict) -> list[dict]:
    recs = []
    band_energy: dict[str, float] = tonal.get("band_energy_db", {})

    if not band_energy:
        return recs

    band_names = list(BAND_LABELS.keys())
    values = [band_energy.get(b) for b in band_names]

    # Проверяем аномально выделяющиеся диапазоны
    valid_values = [v for v in values if v is not None]
    if len(valid_values) < 3:
        return recs

    mean_db = sum(valid_values) / len(valid_values)

    for name, val in zip(band_names, values):
        if val is None:
            continue
        excess = val - mean_db
        if excess > BAND_EXCESS_THRESHOLD:
            label = BAND_LABELS[name]
            recs.append(_rec(
                f"WARN_EXCESS_{name.upper()}",
                "tonal_balance",
                f"Избыток в диапазоне {label}",
                "warning",
                f"Диапазон {label} на {excess:.1f} dB выше среднего уровня. "
                f"{BAND_DESCRIPTIONS.get(name, '')}",
                f"Примените эквализацию: попробуйте убрать {excess:.0f} dB "
                f"на {BAND_FREQ_HINTS.get(name, 'этой')} Гц полосовым фильтром (Q=1.5). "
                "Используйте spectrum analyser (SPAN) для визуального контроля.",
                value=round(excess, 1),
                unit="dB excess",
            ))

    # Spectral centroid — слишком тёмный или слишком яркий
    centroid = tonal.get("spectral_centroid_hz", 0)
    if centroid < 1000:
        recs.append(_rec(
            "INFO_DARK",
            "tonal_balance",
            "Спектральный центр смещён в низкие частоты",
            "info",
            f"Spectral Centroid = {centroid:.0f} Hz. Трек звучит тёмно и глухо. "
            "Высоких частот (presence, air) мало относительно баса.",
            "Добавьте «воздух» — полку (High Shelf) от 8–10 kHz на +2..+3 dB. "
            "Убедитесь, что тарелки и верхние частоты вокала не срезаны.",
            value=centroid,
            unit="Hz",
        ))
    elif centroid > 5000:
        recs.append(_rec(
            "INFO_BRIGHT",
            "tonal_balance",
            "Спектральный центр смещён в высокие частоты",
            "info",
            f"Spectral Centroid = {centroid:.0f} Hz. Трек звучит ярко и резко. "
            "Возможен избыток «цифровой» яркости без плотного баса.",
            "Проверьте баланс: добавьте Low Shelf от 80–100 Hz на +2 dB "
            "или чуть срежьте High Shelf от 10 kHz. Слушайте на разных системах.",
            value=centroid,
            unit="Hz",
        ))
    return recs


def _check_bpm(rhythm: dict) -> list[dict]:
    recs = []
    bpm = rhythm.get("bpm", 0)
    confidence = rhythm.get("beat_confidence", 1.0)

    if bpm < BPM_MIN or bpm > BPM_MAX:
        recs.append(_rec(
            "INFO_BPM_UNCERTAIN",
            "technical",
            "BPM не определён уверенно",
            "info",
            f"Алгоритм определил BPM = {bpm:.1f}, но значение выходит за разумный диапазон. "
            "Возможно, трек сильно синкопирован или темп переменный.",
            "Проверьте BPM вручную в DAW. "
            "Если темп переменный (рубато) — это нормально.",
            value=bpm,
            unit="BPM",
        ))
    elif confidence < 0.3:
        recs.append(_rec(
            "INFO_RHYTHM_WEAK",
            "technical",
            "Слабо выраженный ритм",
            "info",
            f"Уверенность beat-трекера: {confidence:.2f}. "
            "Трек либо медленный ambient/drone, либо очень сложный ритмически.",
            "Если планируете синхронизацию в плейлисте — убедитесь, "
            "что ударные достаточно отчётливы в миксе.",
            value=confidence,
        ))
    return recs


# ── Таблицы описаний ──────────────────────────────────────────────────────────

BAND_LABELS: dict[str, str] = {
    "sub_bass":  "Суббас (20–60 Hz)",
    "bass":      "Бас (60–250 Hz)",
    "low_mid":   "Нижняя середина (250–500 Hz)",
    "mid":       "Середина (500–2000 Hz)",
    "upper_mid": "Верхняя середина (2–6 kHz)",
    "presence":  "Присутствие (6–10 kHz)",
    "air":       "Воздух (10–20 kHz)",
}

BAND_DESCRIPTIONS: dict[str, str] = {
    "sub_bass":  "Суббас добавляет «давление», но на маленьких колонках не слышен. "
                 "Избыток делает микс мутным и монструозным.",
    "bass":      "Бочка и бас-гитара живут здесь. Избыток даёт 'жирный' звук, "
                 "но перегружает мастер-шину и 'заваливает' все остальные инструменты.",
    "low_mid":   "Самый коварный диапазон. Избыток на 200–400 Hz — главная причина "
                 "«мутного» и «коробочного» звучания микса.",
    "mid":       "Вокал, гитары, клавишные. Избыток делает звук «гнусавым» и режущим.",
    "upper_mid": "Диапазон чёткости и атаки. Слишком много — «резкий», болезненный звук. "
                 "Мало — инструменты «тонут» в миксе.",
    "presence":  "Ощущение присутствия. Избыток даёт 'цифровой' неестественный звук.",
    "air":       "Воздух и блеск. Избыток — сибилянс и свист. Мало — тусклый, 'заглушённый' звук.",
}

BAND_FREQ_HINTS: dict[str, str] = {
    "sub_bass":  "30–50",
    "bass":      "80–200",
    "low_mid":   "250–400",
    "mid":       "800–1500",
    "upper_mid": "3000–5000",
    "presence":  "7000–9000",
    "air":       "12000–16000",
}


# ── Публичный API ─────────────────────────────────────────────────────────────

def generate_recommendations(metrics: dict[str, Any], genre: str) -> list[dict[str, Any]]:
    """
    Принимает полный словарь метрик из analyzer.analyze()
    и строит список рекомендаций.

    Args:
        metrics: результат analyzer.analyze()
        genre:   строка жанра ("lo-fi", "modern-pop", "techno")

    Returns:
        Список словарей-рекомендаций, отсортированный по severity:
        high → warning → info
    """
    loudness = metrics.get("loudness", {})
    tonal = metrics.get("tonal", {})
    stereo = metrics.get("stereo", {})
    rhythm = metrics.get("rhythm", {})

    recs: list[dict] = []
    recs.extend(_check_clipping(loudness))
    recs.extend(_check_true_peak(loudness))
    recs.extend(_check_lufs(loudness, genre))
    recs.extend(_check_dynamics(loudness))
    recs.extend(_check_stereo(stereo))
    recs.extend(_check_tonal_balance(tonal))
    recs.extend(_check_bpm(rhythm))

    # Сортировка: high > warning > info
    order = {"high": 0, "warning": 1, "info": 2}
    recs.sort(key=lambda r: order.get(r.get("severity", "info"), 3))

    return recs
