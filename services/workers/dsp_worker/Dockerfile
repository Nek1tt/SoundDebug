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
RUN pip install --no-cache-dir \
        torch==2.3.1+cpu torchaudio==2.3.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Shared-пакет (config, db, storage)
COPY shared/ /app/shared/
COPY data/ /app/data/

# All worker packages are required at import time. The DSP task imports both
# reference_worker and stem_worker even when stem analysis is disabled.
COPY services/workers/ /app/services/workers/
COPY services/__init__.py /app/services/__init__.py

# Celery запускается напрямую
CMD ["celery", "-A", "services.workers.dsp_worker.worker.celery_app", \
     "worker", "--loglevel=info", "--concurrency=1", "--hostname=dsp-worker", "-Q", "dsp"]
