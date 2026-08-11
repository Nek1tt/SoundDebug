"""
shared/storage/s3_client.py
Асинхронный клиент для MinIO (S3-совместимый).
Используется upload-service для сохранения аудиофайлов
и report-service для чтения результатов.

Бакеты (по ERD MINIO_S3_STORAGE):
  uploads/raw audio files  → bucket "uploads", prefix "raw/"
  stems/Demucs output      → bucket "uploads", prefix "stems/"
  genre-curves/reference   → bucket "uploads", prefix "genre-curves/"
"""
import io
from shared.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET

from minio import Minio
from minio.error import S3Error


def get_minio_client() -> Minio:
    """Возвращает синхронный клиент MinIO (minio-py не поддерживает async нативно)."""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,   # В dev-окружении без TLS
    )


def ensure_bucket(client: Minio, bucket: str = MINIO_BUCKET) -> None:
    """Создаёт бакет если не существует."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_file(data: bytes, object_name: str, content_type: str = "audio/mpeg") -> str:
    """
    Загружает bytes в MinIO.
    Возвращает object_name — ключ для последующего доступа.
    """
    client = get_minio_client()
    ensure_bucket(client)
    client.put_object(
        MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def get_presigned_url(object_name: str, expires_seconds: int = 3600) -> str:
    """Возвращает временную ссылку на скачивание файла."""
    from datetime import timedelta
    client = get_minio_client()
    return client.presigned_get_object(
        MINIO_BUCKET,
        object_name,
        expires=timedelta(seconds=expires_seconds),
    )


def delete_file(object_name: str) -> None:
    """Remove an uploaded source/reference after analysis finishes."""
    get_minio_client().remove_object(MINIO_BUCKET, object_name)
