"""
upload-service/main.py — Сервис загрузки аудио и создания джобов. Порт 8002.

Эндпоинты:
  POST /jobs             — создать джоб (загрузить аудио, выбрать жанр)
  GET  /jobs             — список джобов пользователя
  GET  /jobs/{id}        — один джоб
  GET  /jobs/{id}/status — статус из Redis (быстро)
  GET  /health
"""
import pathlib
import uuid
from typing import Optional

import jwt
from celery import Celery
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    REDIS_URL,
    MAX_UPLOAD_MB,
    AUDIO_ML_DEFAULT,
)
from shared.db.session import get_db
from shared.db.models import Job
from shared.storage.redis_client import (
    delete_job_cache,
    get_job_progress,
    get_job_status,
    set_job_status,
)
from shared.storage.s3_client import upload_file

app = FastAPI(title="Upload Service", version="1.0.0")

ALLOWED_GENRES = ["lo-fi", "modern-pop", "hip-hop", "techno", "electronic"]
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_REFERENCES = 3

# ── Celery клиент (только для отправки задач, без воркера) ────────────────────
_celery = Celery(broker=REDIS_URL, backend=REDIS_URL)


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


class JobResponse(BaseModel):
    id: int
    user_id: int
    genre: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    progress: int


@app.get("/health")
async def health():
    return {"status": "ok", "service": "upload"}


@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    genre: str = Form(...),
    file: UploadFile = File(...),
    references: list[UploadFile] = File(default=[]),
    audio_ml_analysis: bool = Form(default=AUDIO_ML_DEFAULT),
    # Kept temporarily for clients from report v1. Demucs is not scheduled.
    stem_analysis: bool = Form(default=False),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if genre not in ALLOWED_GENRES:
        raise HTTPException(status_code=400, detail=f"Unknown genre. Allowed: {ALLOWED_GENRES}")

    if len(references) > MAX_REFERENCES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_REFERENCES} references")

    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported audio format: {ext or 'unknown'}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is larger than {MAX_UPLOAD_MB} MB")
    object_name = f"raw/{uuid.uuid4()}{ext}"
    upload_file(content, object_name, file.content_type or "audio/mpeg")

    reference_keys: list[str] = []
    for reference in references:
        ref_ext = pathlib.Path(reference.filename or "").suffix.lower()
        if ref_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"Unsupported reference format: {ref_ext or 'unknown'}")
        ref_content = await reference.read(MAX_UPLOAD_BYTES + 1)
        if len(ref_content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Reference is larger than {MAX_UPLOAD_MB} MB")
        ref_key = f"references/{uuid.uuid4()}{ref_ext}"
        upload_file(ref_content, ref_key, reference.content_type or "audio/mpeg")
        reference_keys.append(ref_key)

    job = Job(user_id=user_id, genre=genre, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await set_job_status(job.id, "pending")

    # ── Запускаем DSP-воркер ──────────────────────────────────────────────────
    _celery.send_task(
        "dsp_worker.worker.analyze_track",
        kwargs={
            "job_id":  job.id,
            "s3_key":  object_name,
            "genre":   genre,
            "reference_keys": reference_keys,
            "stem_analysis": False,
            "audio_ml_analysis": audio_ml_analysis,
        },
        queue="dsp",
    )

    status = await get_job_status(job.id) or job.status
    return JobResponse(id=job.id, user_id=job.user_id, genre=job.genre, status=status)


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.user_id == user_id).order_by(Job.id.desc()))
    jobs = result.scalars().all()
    response = []
    for job in jobs:
        status = await get_job_status(job.id) or job.status
        response.append(JobResponse(id=job.id, user_id=job.user_id, genre=job.genre, status=status))
    return response


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    current_status = await get_job_status(job.id) or job.status
    return JobResponse(id=job.id, user_id=job.user_id, genre=job.genre, status=current_status)


@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def job_status(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    status = await get_job_status(job_id) or job.status
    progress = await get_job_progress(job_id)
    return JobStatusResponse(job_id=job_id, status=status, progress=progress)


@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    current_status = await get_job_status(job_id) or job.status
    if current_status in {"pending", "processing", "stem-analysis", "retrying"}:
        raise HTTPException(status_code=409, detail="Wait until processing finishes before deleting")
    await db.delete(job)
    await db.commit()
    await delete_job_cache(job_id)
