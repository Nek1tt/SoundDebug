"""
shared/storage/redis_client.py
Обёртка над redis.asyncio.
Используется upload-service и report-service для
хранения быстрого статуса/прогресса джобов.
"""
import redis.asyncio as aioredis

from shared.config import REDIS_URL

# Пул соединений — создаётся один раз при старте приложения
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


# ── Хелперы для статуса / прогресса ──────────────────────────

async def set_job_status(job_id: int, status: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.setex(f"job_status:{job_id}", ttl, status)


async def get_job_status(job_id: int) -> str | None:
    r = await get_redis()
    return await r.get(f"job_status:{job_id}")


async def set_job_progress(job_id: int, progress: int, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.setex(f"job_progress:{job_id}", ttl, str(progress))


async def get_job_progress(job_id: int) -> int:
    r = await get_redis()
    val = await r.get(f"job_progress:{job_id}")
    return int(val) if val is not None else 0


async def delete_job_cache(job_id: int) -> None:
    r = await get_redis()
    await r.delete(f"job_status:{job_id}", f"job_progress:{job_id}")
