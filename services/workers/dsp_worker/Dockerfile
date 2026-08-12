# services/workers/dsp_worker/Dockerfile
#
# Образ тяжелее остальных: librosa тянет за собой scipy, numba, llvmlite.
# Используем python:3.11-slim + системные зависимости для soundfile (libsndfile).

FROM python:3.11-slim AS base

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
COPY data/ /app/data/

# Copy the DSP and reference-comparison packages used by the Celery task.
COPY services/workers/ /app/services/workers/
COPY services/__init__.py /app/services/__init__.py

FROM base AS runtime

CMD ["celery", "-A", "services.workers.dsp_worker.worker.celery_app", \
     "worker", "--loglevel=info", "--concurrency=1", "--hostname=dsp-worker", "-Q", "dsp"]

# Explicit opt-in image for the current no-reference Audio ML experiment.
FROM base AS audio-ml
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY services/workers/dsp_worker/requirements-audio-ml.txt /app/requirements-audio-ml.txt
RUN pip install --no-cache-dir \
        torch==2.3.1+cpu torchaudio==2.3.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /app/requirements-audio-ml.txt
CMD ["celery", "-A", "services.workers.dsp_worker.worker.celery_app", \
     "worker", "--loglevel=info", "--concurrency=1", "--hostname=dsp-worker", "-Q", "dsp"]
