"""
gateway/main.py — API Gateway. Порт 8000.
Единственный публичный порт для фронтенда.

  /auth/*    → auth-service:8001
  /jobs/*    → upload-service:8002
  /reports/* → report-service:8003
  /health    → статус всех сервисов
"""
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from shared.config import AUTH_SERVICE_URL, UPLOAD_SERVICE_URL, REPORT_SERVICE_URL

app = FastAPI(title="API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def startup():
    global _client
    _client = httpx.AsyncClient(timeout=30.0)


@app.on_event("shutdown")
async def shutdown():
    await _client.aclose()


async def _proxy(request: Request, target_url: str) -> Response:
    body = await request.body()
    headers = dict(request.headers)
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


@app.get("/health")
async def health():
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


@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(path: str, request: Request):
    return await _proxy(request, f"{AUTH_SERVICE_URL}/auth/{path}")


@app.api_route("/jobs", methods=["GET", "POST"])
async def proxy_jobs_root(request: Request):
    return await _proxy(request, f"{UPLOAD_SERVICE_URL}/jobs")


@app.api_route("/jobs/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_jobs(path: str, request: Request):
    return await _proxy(request, f"{UPLOAD_SERVICE_URL}/jobs/{path}")


@app.api_route("/reports/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_reports(path: str, request: Request):
    return await _proxy(request, f"{REPORT_SERVICE_URL}/reports/{path}")