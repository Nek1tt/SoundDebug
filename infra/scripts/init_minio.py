"""
infra/scripts/init_minio.py
Создаёт нужные бакеты в MinIO при первом деплое.

Запуск:
  docker compose run --rm upload-service python infra/scripts/init_minio.py
  или вручную: python infra/scripts/init_minio.py
"""
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from minio import Minio
from shared.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY

BUCKETS = [
    "uploads",       # transient source and reference audio
    "genre-curves",  # reference JSON кривые жанров
]


def main():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    for bucket in BUCKETS:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f"✓ Created bucket: {bucket}")
        else:
            print(f"  Bucket already exists: {bucket}")
    print("MinIO init complete.")


if __name__ == "__main__":
    main()
