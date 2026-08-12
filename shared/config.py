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

# Internal worker-to-service authentication. This endpoint is never exposed by
# the public gateway, but the token also prevents lateral writes in the network.
INTERNAL_SERVICE_TOKEN: str = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")

# MVP resource limits
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "50"))
MAX_AUDIO_DURATION_SEC: int = int(os.environ.get("MAX_AUDIO_DURATION_SEC", "900"))
AUDIO_ML_ENABLED: bool = os.environ.get("AUDIO_ML_ENABLED", "false").lower() == "true"
AUDIO_ML_DEFAULT: bool = os.environ.get("AUDIO_ML_DEFAULT", "false").lower() == "true"
AUDIO_ML_CHECKPOINT: str | None = os.environ.get("AUDIO_ML_CHECKPOINT") or None
