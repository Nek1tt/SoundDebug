# services/workers/dsp_worker/Dockerfile
#
# Образ тяжелее остальных: librosa тянет за собой scipy, numba, llvmlite.
# Используем python:3.11-slim + системные зависимости для soundfile (libsndfile).

FROM python:3.11-slim

# Системные зависимости:
#   libsndfile1  — для soundfile (.wav/.flac)
#   ffmpeg       — для librosa (декодирование .mp3/.ogg через audioread / soundfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/workers/dsp_worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Shared-пакет (config, db, storage)
COPY shared/ /app/shared/

# Сам воркер
COPY services/workers/dsp_worker/ /app/services/workers/dsp_worker/
COPY services/workers/__init__.py  /app/services/workers/__init__.py
COPY services/__init__.py          /app/services/__init__.py

# Celery запускается напрямую
CMD ["celery", "-A", "services.workers.dsp_worker.worker.celery_app", \
     "worker", "--loglevel=info", "--concurrency=2", "-Q", "dsp"]
