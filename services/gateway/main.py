"""
services/gateway/main.py
API Gateway. Порт 8000 — единственный публичный порт для фронтенда.

Маршрутизация:
  /auth/*    → auth-service:8001
  /jobs/*    → upload-service:8002
  /reports/* → report-service:8003
  /health    → статус всех сервисов

Фронтенд общается ТОЛЬКО с gateway:8000 и не знает о внутренних портах.
"""
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from shared.config import AUTH_SERVICE_URL, UPLOAD_SERVICE_URL, REPORT_SERVICE_URL

app = FastAPI(title="API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # В prod замените на конкретный домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP-клиент с таймаутом (переиспользуется для всех запросов)
_client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def startup():
    global _client
    _client = httpx.AsyncClient(timeout=30.0)


@app.on_event("shutdown")
async def shutdown():
    await _client.aclose()


# ── Хелпер проксирования ──────────────────────────────────────

async def _proxy(request: Request, target_url: str) -> Response:
    """
    Пробрасывает запрос к целевому сервису, сохраняя:
    - метод (GET/POST/PUT/DELETE)
    - заголовки (включая Authorization)
    - тело запроса
    - query-параметры
    """
    # Для multipart/form-data (загрузка файлов) читаем иначе
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        body = await request.body()
    else:
        body = await request.body()

    headers = dict(request.headers)
    # Убираем заголовки, которые httpx выставит сам
    headers.pop("host", None)
    headers.pop("content-length", None)

    resp = await _client.request(
        method=request.method,
        url=target_url,
        content=body,
        headers=headers,
        params=dict(request.query_params),
    )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


# ── Маршруты ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Проверяет живость всех downstream-сервисов."""
    results = {}
    for name, url in [
        ("auth",   AUTH_SERVICE_URL),
        ("upload", UPLOAD_SERVICE_URL),
        ("report", REPORT_SERVICE_URL),
    ]:
        try:
            r = await _client.get(f"{url}/health", timeout=3.0)
            results[name] = "ok" if r.status_code == 200 else "degraded"
        except Exception:
            results[name] = "unavailable"
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}


# /auth/* → auth-service
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(path: str, request: Request):
    return await _proxy(request, f"{AUTH_SERVICE_URL}/auth/{path}")


# /jobs/* → upload-service
@app.api_route("/jobs", methods=["GET", "POST"])
async def proxy_jobs_root(request: Request):
    return await _proxy(request, f"{UPLOAD_SERVICE_URL}/jobs")


@app.api_route("/jobs/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_jobs(path: str, request: Request):
    return await _proxy(request, f"{UPLOAD_SERVICE_URL}/jobs/{path}")


# /reports/* → report-service
@app.api_route("/reports/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_reports(path: str, request: Request):
    return await _proxy(request, f"{REPORT_SERVICE_URL}/reports/{path}")
