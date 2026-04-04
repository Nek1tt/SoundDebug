"""
upload-service/main.py — Сервис загрузки аудио и создания джобов. Порт 8002.

Эндпоинты:
  POST /jobs             — создать джоб (загрузить аудио, выбрать жанр)
  GET  /jobs             — список джобов пользователя
  GET  /jobs/{id}        — один джоб
  GET  /jobs/{id}/status — статус из Redis (быстро)
  GET  /health
"""
import uuid
import pathlib
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import JWT_SECRET, JWT_ALGORITHM
from shared.db.session import get_db
from shared.db.models import Job
from shared.storage.redis_client import set_job_status, get_job_status, get_job_progress
from shared.storage.s3_client import upload_file

app = FastAPI(title="Upload Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_GENRES = ["lo-fi", "modern-pop", "techno"]


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
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if genre not in ALLOWED_GENRES:
        raise HTTPException(status_code=400, detail=f"Unknown genre. Allowed: {ALLOWED_GENRES}")

    content = await file.read()
    ext = pathlib.Path(file.filename).suffix or ".mp3"
    object_name = f"raw/{uuid.uuid4()}{ext}"
    upload_file(content, object_name, file.content_type or "audio/mpeg")

    job = Job(user_id=user_id, genre=genre, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await set_job_status(job.id, "pending")
    return JobResponse(id=job.id, user_id=job.user_id, genre=job.genre, status=job.status)


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.user_id == user_id))
    jobs = result.scalars().all()
    return [JobResponse(id=j.id, user_id=j.user_id, genre=j.genre, status=j.status) for j in jobs]


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(id=job.id, user_id=job.user_id, genre=job.genre, status=job.status)


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