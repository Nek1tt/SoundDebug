"""
shared/config.py
Централизованная конфигурация через переменные окружения.
Каждый сервис импортирует нужные ему настройки отсюда.
"""
import os


# ── База данных ────────────────────────────────────────────────
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://admin:secret@localhost:5432/musicdb",
)

# ── Redis ──────────────────────────────────────────────────────
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── MinIO / S3 ─────────────────────────────────────────────────
MINIO_ENDPOINT: str   = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET: str     = os.environ.get("MINIO_BUCKET", "uploads")

# ── JWT ────────────────────────────────────────────────────────
JWT_SECRET: str        = os.environ.get("JWT_SECRET", "supersecretkey")
JWT_ALGORITHM: str     = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

# ── URL внутренних сервисов (используются в gateway) ──────────
AUTH_SERVICE_URL: str   = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
UPLOAD_SERVICE_URL: str = os.environ.get("UPLOAD_SERVICE_URL", "http://localhost:8002")
REPORT_SERVICE_URL: str = os.environ.get("REPORT_SERVICE_URL", "http://localhost:8003")
