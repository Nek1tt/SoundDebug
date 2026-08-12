"""P0 explainable diagnostic engine.

Every conclusion is explicitly classified as a directly measured fact, an
observed reference difference, or a hypothesis that must be auditioned.
Processing values are never inferred from a stereo master.
"""

from __future__ import annotations

from typing import Any

FACT = "FACT"
REFERENCE_DIFFERENCE = "REFERENCE_DIFFERENCE"
HYPOTHESIS = "HYPOTHESIS"

TRUE_PEAK_CONTEXT_DBTP = -1.0
PLR_DENSE_CONTEXT_LU = 7.0
DC_OFFSET_LIMIT = 0.01
MONO_LOSS_LIMIT_DB = -3.0
BASS_SIDE_LIMIT_PCT = 25.0
TONAL_DIFFERENCE_LIMIT_DB = 3.0

BAND_LABELS = {
    "sub_bass": "суббасе 20–60 Гц",
    "bass": "басе 60–250 Гц",
    "low_mid": "нижней середине 250–500 Гц",
    "mid": "середине 500 Гц–2 кГц",
    "upper_mid": "верхней середине 2–6 кГц",
    "presence": "области presence 6–10 кГц",
    "air": "области air 10–20 кГц",
}

PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
CLASS_ORDER = {FACT: 0, HYPOTHESIS: 1, REFERENCE_DIFFERENCE: 2}


def _card(
    code: str,
    classification: str,
    category: str,
    title: str,
    priority: str,
    reliability: str,
    reliability_reason: str,
    what_detected: str,
    why_attention: str,
    audible_meaning: str,
    possible_causes: list[str],
    daw_check_steps: list[str],
    do_not_automate: str,
    *,
    evidence: list[str],
    timestamps: list[float] | None = None,
    reference_context: str | None = None,
) -> dict[str, Any]:
    if classification not in {FACT, REFERENCE_DIFFERENCE, HYPOTHESIS}:
        raise ValueError(f"Unsupported finding class: {classification}")
    return {
        "id": code,
        "classification": classification,
        "category": category,
        "title": title,
        "priority": priority,
        "severity": {"CRITICAL": "high", "HIGH": "warning", "MEDIUM": "info", "LOW": "info"}[priority],
        "reliability": reliability,
        "reliability_reason": reliability_reason,
        "what_detected": what_detected,
        "why_attention": why_attention,
        "audible_meaning": audible_meaning,
        "possible_causes": possible_causes,
        "daw_check_steps": daw_check_steps,
        "do_not_automate": do_not_automate,
        "reference_context": reference_context,
        "evidence": evidence,
        "timestamps_sec": timestamps or [],
    }


def _facts(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    loudness = metrics.get("loudness", {})
    stereo = metrics.get("stereo", {})
    meta = metrics.get("meta", {})
    result: list[dict[str, Any]] = []

    count = int(loudness.get("clipping_count") or 0)
    if count:
        events = loudness.get("clipping_events", [])
        result.append(_card(
            "FACT_SAMPLE_CLIPPING", FACT, "technical", "В файле найдены отсечённые сэмплы", "CRITICAL",
            "DIRECT", "Состояние непосредственно измерено в декодированном waveform.",
            f"{count} сэмплов достигли порога 0.999 FS; они объединены в {len(events)} участков.",
            "Плоская вершина waveform может быть уже записана в экспорт и не восстанавливается уменьшением громкости готового файла.",
            "Иногда это слышно как жёсткий щелчок или искажение транзиента; иногда отдельные сэмплы остаются неслышимыми.",
            ["перегруз до master fader", "жёсткий limiter/clipper", "ошибка gain staging или экспорта"],
            ["Откройте перечисленные места на sample level.", "Сравните waveform до и после limiter/clipper.", "Сделайте новый экспорт с запасом и проверьте, исчезло ли отсечение.", "Сравните версии на одинаковой воспринимаемой громкости."],
            "Не уменьшайте master fader после уже перегруженной цепи и не считайте, что это восстановит форму волны.",
            evidence=[f"samples >= 0.999 FS: {count}", f"regions: {len(events)}"],
            timestamps=[float(item["start_sec"]) for item in events[:8]],
        ))

    peak = loudness.get("true_peak_dbtp", loudness.get("true_peak_db"))
    if peak is not None and float(peak) > TRUE_PEAK_CONTEXT_DBTP:
        result.append(_card(
            "FACT_TRUE_PEAK_MARGIN", FACT, "delivery", "True-peak запас меньше контекста −1 dBTP", "HIGH",
            "MEASURED_ESTIMATE", "Это 4× oversampled estimate, а не сертифицированный meter.",
            f"Максимальная 4× оценка составляет {float(peak):.2f} dBTP — выше delivery-контекста −1 dBTP.",
            "Малый inter-sample запас повышает вероятность overs после кодирования, но −1 dBTP не является универсальной художественной нормой.",
            "После lossy-кодирования могут появиться краткие перегрузы или жёсткость на пиках.",
            ["высокий limiter ceiling", "агрессивное ограничение пиков", "межсэмпловое восстановление после кодека"],
            ["Проверьте файл сертифицированным true-peak meter.", "Сделайте codec preview для целевой площадки.", "Экспортируйте вариант с большим ceiling margin.", "Сравните варианты после loudness matching."],
            "Не считайте −1 dBTP обязательной целью для любого формата и не меняйте limiter только по одному числу.",
            evidence=[f"4x true-peak estimate: {float(peak):.2f} dBTP", "delivery context: -1 dBTP"],
        ))

    offsets = [abs(float(value)) for value in loudness.get("dc_offset_by_channel", [])]
    if offsets and max(offsets) > DC_OFFSET_LIMIT:
        result.append(_card(
            "FACT_DC_OFFSET", FACT, "technical", "Обнаружен DC offset", "HIGH", "DIRECT",
            "Среднее значение waveform по каналу измерено напрямую.",
            f"Максимальное абсолютное смещение канала составляет {max(offsets):.4f} FS.",
            "DC offset уменьшает симметричный headroom и может указывать на проблему раньше в цепи.",
            "Обычно сам DC не воспринимается как музыкальный тон, но может влиять на обработку и доступный headroom.",
            ["асимметричный waveshaper", "ошибка записи или плагина", "некорректная обработка инфраниза"],
            ["Проверьте анализатором сигнал до master processing.", "Найдите первый этап цепи, где появляется смещение.", "Сравните корректно удалённый DC вариант на одинаковой громкости."],
            "Не ставьте произвольный high-pass на слышимую частоту: сначала локализуйте источник.",
            evidence=[f"max absolute channel mean: {max(offsets):.4f} FS"],
        ))

    layout = stereo.get("channel_layout")
    if layout in {"mono", "dual-mono"} or stereo.get("is_mono") is True:
        label = "один канал" if layout == "mono" or int(meta.get("num_channels") or 1) == 1 else "два практически одинаковых канала (dual mono)"
        result.append(_card(
            "FACT_MONO_LAYOUT", FACT, "stereo", "Экспорт фактически моно", "HIGH" if layout == "dual-mono" else "MEDIUM",
            "DIRECT", "Количество каналов и M/S-энергия измерены непосредственно.",
            f"Файл содержит {label}; Side-энергия практически отсутствует.",
            "Для ожидаемого mono master это нормальное состояние. Для полного музыкального mix/master это может быть ошибкой маршрутизации или экспорта.",
            "Панорама и пространственные различия между каналами отсутствуют или почти отсутствуют.",
            ["намеренный mono master", "экспорт mono bus", "дублирование одного mono-канала в L/R", "схлопывание stereo processing"],
            ["Сравните файл с playback внутри DAW.", "Проверьте формат master bus и export channel mode.", "Solo Side: убедитесь, что там действительно нет ожидаемого материала.", "Повторно экспортируйте короткий фрагмент и сравните channel layout."],
            "Не добавляйте stereo widener, пока не проверена маршрутизация: он не восстановит потерянную stereo information.",
            evidence=[f"channel layout: {layout or 'mono'}", f"channel count: {meta.get('num_channels')}", f"stereo width: {float(stereo.get('stereo_width') or 0):.4f}"],
        ))
    return result


def _technical_hypotheses(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    loudness = metrics.get("loudness", {})
    stereo = metrics.get("stereo", {})
    result: list[dict[str, Any]] = []
    plr = loudness.get("plr_lu")
    if plr is not None and float(plr) < PLR_DENSE_CONTEXT_LU:
        result.append(_card(
            "HYP_DENSE_DYNAMICS", HYPOTHESIS, "dynamics", "Проверьте, не потерялись ли транзиенты", "MEDIUM",
            "MEDIUM", "Гипотеза основана на PLR; без прослушивания она не доказывает over-compression.",
            f"PLR составляет {float(plr):.1f} LU: true peak расположен близко к integrated loudness.",
            "Низкий PLR совместим с плотным мастерингом, но также возникает из-за аранжировки и намеренной эстетики.",
            "Возможны менее выраженные атаки, ощущение постоянной плотности или утомляемость; но плотный жанровый мастер может звучать корректно.",
            ["limiter с большой gain reduction", "быстрый bus compressor", "плотная аранжировка", "намеренно ровная динамика"],
            ["Сделайте loudness-matched A/B с референсами.", "Послушайте kick/snare и другие атаки на коротком loop.", "Временно bypass limiter и bus compression с компенсацией громкости.", "Если атаки возвращаются, по одному включайте stages и найдите источник.", "Сохраните новую версию и повторите A/B."],
            "Не увеличивайте attack/release и не ослабляйте compressor по готовому числу PLR.",
            evidence=[f"PLR: {float(plr):.1f} LU"],
        ))

    minimum = float(stereo.get("minimum_phase_correlation", 1.0))
    mono_loss = float(stereo.get("mono_fold_down_loss_db", 0.0))
    risks = stereo.get("phase_risk_segments", [])
    if minimum < 0.0 or mono_loss < MONO_LOSS_LIMIT_DB:
        result.append(_card(
            "HYP_MONO_CANCELLATION", HYPOTHESIS, "stereo", "Проверьте потерю элементов в mono", "HIGH",
            "HIGH" if minimum < -0.2 else "MEDIUM", "Корреляция и fold-down измерены; слышимость и источник требуют проверки.",
            f"Минимальная 3-секундная L/R correlation = {minimum:.2f}; общий mono fold-down меняет RMS на {mono_loss:.1f} dB.",
            "Два независимых признака указывают, что часть Side information может компенсироваться при суммировании каналов.",
            "В mono отдельные элементы могут стать тише, потерять тело или изменить тембр.",
            ["polarity mismatch", "short-delay widening", "decorrelation/reverb", "противофазный слой синтезатора"],
            ["Переключите master в mono в отмеченных местах.", "Назовите элемент, который меняется, до открытия анализаторов.", "По очереди bypass widening, stereo delay и reverb returns.", "Проверьте polarity и M/S routing найденного источника.", "Сравните исправленный вариант в stereo и mono на одинаковой громкости."],
            "Не сужайте весь master автоматически: проблема может быть локальной и художественно оправданной.",
            evidence=[f"minimum 3 s correlation: {minimum:.2f}", f"mono fold-down RMS difference: {mono_loss:.1f} dB"],
            timestamps=[float(item["time_sec"]) for item in risks[:10]],
        ))

    bass_side = float(stereo.get("bass_side_energy_pct", 0.0))
    if bass_side > BASS_SIDE_LIMIT_PCT:
        result.append(_card(
            "HYP_LOW_END_SIDE", HYPOTHESIS, "stereo", "Проверьте фокус low-end в mono", "MEDIUM", "MEDIUM",
            "Side share ниже 150 Гц измерен, но допустимость зависит от материала и формата.",
            f"{bass_side:.1f}% низкочастотной M/S-энергии находится в Side.",
            "Значительная низкочастотная Side-энергия иногда связана с менее стабильным центром и mono cancellation.",
            "Bass/kick могут ощущаться менее сфокусированными или меняться при mono playback.",
            ["стерео-синтезатор", "widening на bass bus", "room/reverb в низах", "различающиеся L/R слои"],
            ["Прослушайте low-passed Side отдельно.", "Переключите low-end в mono и сравните на равной громкости.", "Поочерёдно отключите пространственную обработку низкочастотных источников.", "Оставьте изменение только если фокус улучшается без потери нужной ширины."],
            "Не применяйте mono-maker ко всему диапазону до 150 Гц автоматически.",
            evidence=[f"Side energy below 150 Hz: {bass_side:.1f}%"],
        ))
    return result


def _reference_context(item: dict[str, Any]) -> str:
    return (
        f"{item.get('support_count', 0)} из {item.get('reference_count', 0)} референсов поддерживают направление. "
        f"{item.get('reliability_reason', '')}"
    ).strip()


def _reference_findings(comparison: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not comparison or comparison.get("source") != "references":
        return []
    result: list[dict[str, Any]] = []
    loudness = comparison.get("loudness_difference")
    if loudness and abs(float(loudness["difference"])) >= 2.0:
        delta = float(loudness["difference"])
        direction = "громче" if delta > 0 else "тише"
        result.append(_card(
            "REF_LOUDNESS", REFERENCE_DIFFERENCE, "loudness", "Громкость отличается от выбранных референсов", "LOW",
            loudness["reliability"], loudness["reliability_reason"],
            f"Integrated loudness target на {abs(delta):.1f} LU {direction} медианы референсов.",
            "Разница сохранена отдельно и не влияет на tonal-shape comparison. Это контекст релиза, а не ошибка.",
            "При несогласованном уровне более громкая версия почти всегда кажется детальнее и лучше, что искажает A/B.",
            ["другая стадия мастеринга", "разные delivery targets", "иной crest factor", "разница в аранжировке"],
            ["Выровняйте perceived loudness target и референсов.", "Сравнивайте одинаково плотные секции.", "Решите, соответствует ли уровень конкретной площадке и версии mix/master."],
            "Не подгоняйте LUFS под жанр и не усиливайте limiter только ради совпадения с референсом.",
            evidence=[f"target - reference median: {delta:+.1f} LU", f"reference MAD: {float(loudness['reference_mad']):.1f} LU"],
            reference_context=_reference_context(loudness),
        ))

    for name, item in comparison.get("dynamics_difference", {}).items():
        delta = float(item["difference"])
        if abs(delta) < 1.5:
            continue
        label = {"plr": "PLR", "short_term_loudness_spread": "P95–P10 short-term loudness spread", "crest_factor": "crest factor"}.get(name, name)
        result.append(_card(
            f"REF_DYNAMICS_{name.upper()}", REFERENCE_DIFFERENCE, "dynamics", f"{label} отличается от референсов", "LOW",
            item["reliability"], item["reliability_reason"],
            f"Разница target относительно медианы референсов: {delta:+.1f} {item['unit']}.",
            "SoundDebug хранит dynamics отдельно от loudness и tonal shape, чтобы не смешивать разные свойства мастера.",
            "Разница может соответствовать более плотным или более свободным транзиентам, но направление нужно подтвердить слухом.",
            ["limiting/compression", "плотность аранжировки", "разные секции треков", "намеренная динамическая эстетика"],
            ["Сделайте loudness-matched A/B.", "Сравните похожие по функции секции.", "Проверьте transient и bus processing через compensated bypass.", "Зафиксируйте, стало ли восприятие лучше, а не только ближе по числу."],
            "Не переносите численную разницу в threshold, ratio, attack или release компрессора.",
            evidence=[f"difference: {delta:+.1f} {item['unit']}", f"reference MAD: {float(item['reference_mad']):.1f} {item['unit']}"],
            reference_context=_reference_context(item),
        ))

    for name, item in comparison.get("stereo_difference", {}).items():
        thresholds = {"width": 0.15, "phase_correlation": 0.15, "mono_fold_down": 1.0, "bass_side_energy": 10.0}
        delta = float(item["difference"])
        if abs(delta) < thresholds.get(name, 1.0):
            continue
        label = {"width": "Stereo width", "phase_correlation": "L/R correlation", "mono_fold_down": "Mono fold-down", "bass_side_energy": "Side-энергия low-end"}.get(name, name)
        result.append(_card(
            f"REF_STEREO_{name.upper()}", REFERENCE_DIFFERENCE, "stereo", f"{label} отличается от референсов", "LOW",
            item["reliability"], item["reliability_reason"],
            f"Разница target относительно медианы референсов: {delta:+.2f} {item['unit']}.",
            "Это наблюдаемое пространственное отличие, а не признак качества само по себе.",
            "Target может ощущаться шире, уже или иначе вести себя в mono — в зависимости от самой метрики.",
            ["панорама и аранжировка", "stereo ambience", "widening", "различия секций или исходников"],
            ["Сравните одинаковые секции после loudness matching.", "Переключайте stereo/mono и отмечайте конкретные исчезающие элементы.", "Проверяйте источники и spatial returns по одному."],
            "Не копируйте width или M/S processing референса на весь master автоматически.",
            evidence=[f"difference: {delta:+.2f} {item['unit']}"], reference_context=_reference_context(item),
        ))

    outliers = comparison.get("outlier_segments", [])
    for band, item in comparison.get("tonal_shape_difference", {}).items():
        delta = float(item["difference_db"])
        if abs(delta) < TONAL_DIFFERENCE_LIMIT_DB:
            continue
        direction = "выше" if delta > 0 else "ниже"
        label = BAND_LABELS.get(band, band)
        reliability = item["reliability"]
        classification = HYPOTHESIS if reliability in {"MEDIUM", "HIGH"} and int(item["support_count"]) >= 2 else REFERENCE_DIFFERENCE
        title = f"Проверьте накопление энергии в {label}" if classification == HYPOTHESIS and delta > 0 else f"Устойчивая тональная разница в {label}" if classification == HYPOTHESIS else f"Тональная разница в {label}"
        audible = (
            "Такое соотношение иногда воспринимается как warmth, fullness или плотность, но при накоплении может уменьшать разделение и читаемость."
            if band == "low_mid" and delta > 0 else
            "Изменение может восприниматься как другой вес, яркость или читаемость, но художественный результат зависит от аранжировки."
        )
        result.append(_card(
            f"{'HYP' if classification == HYPOTHESIS else 'REF'}_TONAL_{band.upper()}", classification, "tonal_balance", title,
            "HIGH" if classification == HYPOTHESIS and abs(delta) >= 6 and reliability == "HIGH" else "MEDIUM" if classification == HYPOTHESIS else "LOW",
            reliability, item["reliability_reason"],
            f"Относительная спектральная форма target в {label} на {abs(delta):.1f} dB {direction} медианы референсов после исключения общей громкости.",
            f"Направление проверяется отдельно по каждому треку: {item['support_count']} из {item['reference_count']} референсов показывают значимое отличие в ту же сторону.",
            audible,
            ["баланс уровней источников", "регистр и аранжировка", "вокал, гитары или бас", "reverb tails", "EQ/saturation в отдельных цепях"],
            ["Сделайте loudness-matched A/B с каждым референсом.", "Сравните сходные по плотности секции, а не случайные моменты.", f"Найдите источники, занимающие область {label}.", "Временно bypass или ослабьте соответствующие processing chains по одному.", "Оцените, улучшилась ли читаемость, и только затем сохраните новую версию.", "Повторно запустите SoundDebug и проверьте направление изменения."],
            f"Не вырезайте автоматически {abs(delta):.1f} dB: reference difference не является требуемым EQ gain и не задаёт Q.",
            evidence=[f"relative-shape difference: {delta:+.1f} dB", f"support: {item['support_count']}/{item['reference_count']}", f"reference MAD: {float(item['reference_mad_db']):.1f} dB"],
            timestamps=[float(value["time_sec"]) for value in outliers if value.get("band") == band][:8],
            reference_context=_reference_context(item),
        ))
    return result


def _audio_ml(audio_ml: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not audio_ml or not audio_ml.get("enabled") or not audio_ml.get("scores"):
        return []
    pq = audio_ml["scores"].get("PQ")
    if pq is None:
        return []
    rounded = round(float(pq), 1)
    return [_card(
        "HYP_AUDIOBOX_PQ", HYPOTHESIS, "audio_ml", "Экспериментальная ML-оценка production quality", "LOW", "UNCALIBRATED",
        "Модель не возвращает доверительный интервал для конкретного трека; SoundDebug не подставляет выдуманный confidence.",
        f"Audiobox Aesthetics предсказал PQ примерно {rounded:.1f}/10.",
        "Это субъективный no-reference signal. Он не локализует проблему и не доказывает качество сведения.",
        "Результат полезнее всего как дополнительная ось при сравнении версий одного и того же трека.",
        ["техническое качество и кодирование", "жанровое смещение модели", "аранжировка и запись", "сведение и мастеринг вместе"],
        ["Сохраните оценку текущей версии.", "Измените только одну подтверждённую проблему.", "Сделайте loudness-matched blind A/B.", "Повторите ML-анализ и учитывайте score только вместе с DSP и предпочтением слушателя."],
        "Не оптимизируйте трек ради роста model score и не интерпретируйте его как процент профессионального качества.",
        evidence=[f"Audiobox PQ rounded display: {rounded:.1f}/10"],
    )]


def generate_findings(
    metrics: dict[str, Any], genre: str | None = None, comparison: dict[str, Any] | None = None,
    audio_ml: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return all findings in deterministic priority order; genre is context only."""
    findings = [*_facts(metrics), *_technical_hypotheses(metrics), *_reference_findings(comparison), *_audio_ml(audio_ml)]
    findings.sort(key=lambda item: (
        PRIORITY_ORDER[item["priority"]], CLASS_ORDER[item["classification"]], item["id"],
    ))
    return findings


def split_priority_findings(findings: list[dict[str, Any]], limit: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep the main screen bounded without discarding lower-priority evidence."""
    return findings[:limit], findings[limit:]


# Compatibility entrypoint for integrations that still import this name.
def generate_recommendations(
    metrics: dict[str, Any], genre: str | None = None, comparison: dict[str, Any] | None = None,
    audio_ml: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return generate_findings(metrics, genre, comparison, audio_ml)
