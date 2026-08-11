"""
services/workers/dsp_worker/worker.py

Celery-воркер DSP-анализа.

Задача: analyze_track
  1. Скачивает аудиофайл из MinIO по s3_key
  2. Запускает DSP-анализ (analyzer.py)
  3. Генерирует рекомендации (recommendations.py)
  4. Обновляет статус в Redis на каждом шаге
  5. Отправляет результат в report-service (POST /reports/{job_id})

Запуск воркера:
  celery -A services.workers.dsp_worker.worker worker \
         --loglevel=info --concurrency=2 -Q dsp

Или через docker-compose:
  command: ["celery", "-A", "worker", "worker", "--loglevel=info", "-Q", "dsp"]
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx
from celery import Celery

# Импорты из shared (доступны через PYTHONPATH=/app)
from shared.config import (
    REDIS_URL,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    REPORT_SERVICE_URL,
    INTERNAL_SERVICE_TOKEN,
    DEMUCS_MODEL,
)
from shared.storage.s3_client import delete_file, get_minio_client

from .analyzer import analyze
from .recommendations import generate_recommendations
from services.workers.reference_worker.curve_matcher import compare_to_genre, compare_to_references
from services.workers.stem_worker.demucs_runner import separate_and_analyze

logger = logging.getLogger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "dsp_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={"dsp_worker.worker.analyze_track": {"queue": "dsp"}},
    worker_prefetch_multiplier=1,   # обрабатываем по одному — задачи тяжёлые
    task_acks_late=True,            # подтверждаем только после выполнения
)

# ── Redis helpers (синхронные через redis-py, не async) ───────────────────────

import redis as _redis_sync

_redis_client: _redis_sync.Redis | None = None


def _get_redis() -> _redis_sync.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = _redis_sync.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _set_status(job_id: int, status: str, ttl: int = 3600) -> None:
    _get_redis().setex(f"job_status:{job_id}", ttl, status)


def _set_progress(job_id: int, progress: int, ttl: int = 3600) -> None:
    _get_redis().setex(f"job_progress:{job_id}", ttl, str(progress))


# ── Отправка результата в report-service ──────────────────────────────────────

def _post_report(job_id: int, metrics: dict) -> bool:
    """
    POST /reports/{job_id}
    Возвращает True при успехе.
    """
    url = f"{REPORT_SERVICE_URL}/reports/{job_id}"
    try:
        resp = httpx.post(
            url,
            json={"metrics": metrics},
            headers={"X-Service-Token": INTERNAL_SERVICE_TOKEN},
            timeout=30.0,
        )
        if resp.status_code in (200, 201):
            return True
        logger.error(f"[DSP] report-service returned {resp.status_code}: {resp.text}")
        return False
    except Exception as exc:
        logger.error(f"[DSP] Failed to post report: {exc}")
        return False


# ── MinIO: скачать файл ───────────────────────────────────────────────────────

def _download_from_minio(s3_key: str, dest_path: str) -> None:
    client = get_minio_client()
    client.fget_object(MINIO_BUCKET, s3_key, dest_path)


# ── Celery-задача ─────────────────────────────────────────────────────────────

@celery_app.task(
    name="dsp_worker.worker.analyze_track",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def analyze_track(
    self,
    job_id: int,
    s3_key: str,
    genre: str,
    reference_keys: list[str] | None = None,
    stem_analysis: bool = False,
) -> dict:
    """
    Основная задача DSP-анализа.

    Args:
        job_id:  ID джоба из таблицы job
        s3_key:  Ключ объекта в MinIO (например "raw/uuid.mp3")
        genre:   Жанр ("lo-fi", "modern-pop", "techno")

    Returns:
        Словарь результата (также пишется в report-service)
    """
    reference_keys = reference_keys or []
    cleanup_keys = [s3_key, *reference_keys]
    cleanup_uploads = False
    logger.info(f"[DSP] Task started: job_id={job_id}, s3_key={s3_key}, genre={genre}")

    try:
        # ── Шаг 1: обновляем статус ────────────────────────────────────────
        _set_status(job_id, "processing")
        _set_progress(job_id, 5)

        # ── Шаг 2: скачиваем файл из MinIO ────────────────────────────────
        with tempfile.TemporaryDirectory(prefix=f"sounddebug-{job_id}-") as temp_dir:
            tmp_path = str(Path(temp_dir) / f"target{Path(s3_key).suffix or '.mp3'}")
            _download_from_minio(s3_key, tmp_path)
            _set_progress(job_id, 20)
            logger.info(f"[DSP] Downloaded: {s3_key} → {tmp_path}")

            # ── Шаг 3: DSP-анализ ──────────────────────────────────────────
            _set_progress(job_id, 30)
            dsp_metrics = analyze(tmp_path)
            _set_progress(job_id, 55)
            logger.info(f"[DSP] Analysis done: job_id={job_id}")

            reference_metrics = []
            for index, reference_key in enumerate(reference_keys):
                ref_path = str(Path(temp_dir) / f"reference-{index}{Path(reference_key).suffix or '.mp3'}")
                _download_from_minio(reference_key, ref_path)
                reference_metrics.append(analyze(ref_path))
            reference_comparison = (
                compare_to_references(dsp_metrics, reference_metrics)
                or compare_to_genre(dsp_metrics, genre)
            )
            _set_progress(job_id, 70)

            stem_result = {"enabled": False, "reason": "not requested"}
            if stem_analysis:
                _set_status(job_id, "stem-analysis")
                stem_result = separate_and_analyze(
                    tmp_path,
                    Path(temp_dir) / "demucs",
                    model=DEMUCS_MODEL,
                )
            _set_progress(job_id, 88)

        # ── Шаг 4: генерируем рекомендации ────────────────────────────────
        recommendations = generate_recommendations(dsp_metrics, genre)
        _set_progress(job_id, 92)

        # ── Шаг 5: собираем финальный отчёт ───────────────────────────────
        full_report = {
            **dsp_metrics,
            "genre": genre,
            "reference_comparison": reference_comparison,
            "stem_analysis": stem_result,
            "recommendations": recommendations,
            "report_version": "mvp-1",
            "artistic_intent_warning": (
                "SoundDebug detects measurable deviations, not artistic mistakes. "
                "Check every recommendation against your intent and listening context."
            ),
        }

        # ── Шаг 6: отправляем в report-service ────────────────────────────
        success = _post_report(job_id, full_report)
        if not success:
            _set_status(job_id, "failed")
            raise RuntimeError(f"Failed to post report for job_id={job_id}")

        _set_status(job_id, "done")
        _set_progress(job_id, 100)
        logger.info(f"[DSP] Completed: job_id={job_id}")

        cleanup_uploads = True
        return full_report

    except Exception as exc:
        logger.exception(f"[DSP] Task failed: job_id={job_id}: {exc}")
        exhausted = self.request.retries >= self.max_retries
        _set_status(job_id, "failed" if exhausted else "retrying")
        cleanup_uploads = exhausted
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)

    finally:
        # MVP privacy rule: source audio and references are transient. Reports
        # keep only derived metrics. Cleanup failure must not erase a valid report.
        if cleanup_uploads:
            for object_key in cleanup_keys:
                try:
                    delete_file(object_key)
                except Exception as cleanup_exc:
                    logger.warning("[DSP] Could not delete %s: %s", object_key, cleanup_exc)
