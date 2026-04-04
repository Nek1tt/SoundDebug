"""
shared/db/session.py
Асинхронная сессия SQLAlchemy для PostgreSQL.
Каждый сервис вызывает get_db() как FastAPI dependency.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.config import DATABASE_URL

# Движок подключения. echo=False в prod — не логировать каждый SQL
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Фабрика сессий — expire_on_commit=False важно для async
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency: открывает сессию, закрывает после запроса."""
    async with AsyncSessionLocal() as session:
        yield session
