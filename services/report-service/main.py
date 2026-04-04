"""
report-service/main.py — Сервис репортов. Порт 8003.

Эндпоинты:
  GET  /reports/{job_id}  — получить репорт по джобу
  POST /reports/{job_id}  — создать/обновить репорт (вызывается воркером)
  GET  /health
"""
from typing import Optional, Any

import jwt
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import JWT_SECRET, JWT_ALGORITHM
from shared.db.session import get_db
from shared.db.models import Job, Report

app = FastAPI(title="Report Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


class ReportResponse(BaseModel):
    job_id: int
    metrics: dict[str, Any]


class CreateReportRequest(BaseModel):
    metrics: dict[str, Any]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "report"}


@app.get("/reports/{job_id}", response_model=ReportResponse)
async def get_report(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    report = await db.get(Report, job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not ready yet")
    return ReportResponse(job_id=job_id, metrics=report.metrics)


@app.post("/reports/{job_id}", response_model=ReportResponse, status_code=201)
async def create_report(
    job_id: int,
    body: CreateReportRequest,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    report = await db.get(Report, job_id)
    if report:
        report.metrics = body.metrics
    else:
        report = Report(job_id=job_id, metrics=body.metrics)
        db.add(report)
    job.status = "done"
    await db.commit()
    await db.refresh(report)
    return ReportResponse(job_id=job_id, metrics=report.metrics)