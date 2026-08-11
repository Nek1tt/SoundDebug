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
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import JWT_SECRET, JWT_ALGORITHM, INTERNAL_SERVICE_TOKEN
from shared.db.session import get_db
from shared.db.models import Feedback, Job, Report

app = FastAPI(title="Report Service", version="1.0.0")

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


class FeedbackRequest(BaseModel):
    rating: int
    comment: str = ""


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


@app.post("/reports/{job_id}/feedback", status_code=201)
async def save_feedback(
    job_id: int,
    body: FeedbackRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    job = await db.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    feedback = await db.get(Feedback, job_id)
    if feedback:
        feedback.rating = body.rating
        feedback.comment = body.comment[:1000]
    else:
        db.add(Feedback(job_id=job_id, rating=body.rating, comment=body.comment[:1000]))
    await db.commit()
    return {"job_id": job_id, "saved": True}


@app.post("/reports/{job_id}", response_model=ReportResponse, status_code=201)
async def create_report(
    job_id: int,
    body: CreateReportRequest,
    x_service_token: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if x_service_token != INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
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
