"""
shared/db/models.py
ORM-модели, точно отражающие ERD-схему.
Импортируются в каждом сервисе, который работает с БД.
"""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """
    Таблица USER.
    password — bcrypt-хеш, никогда не возвращается в API-ответах.
    """
    __tablename__ = "user"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    email    = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)   # bcrypt hash

    jobs = relationship("Job", back_populates="user", cascade="all, delete")


class Job(Base):
    """
    Таблица JOB.
    user_id — FK на User (PK + FK в терминах ERD).
    genre   — жанр, выбранный пользователем для сравнения.
    status  — текущий статус: pending / processing / done / failed.
    """
    __tablename__ = "job"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    genre   = Column(String(50), nullable=False)
    status  = Column(String(20), nullable=False, default="pending")

    user   = relationship("User", back_populates="jobs")
    report = relationship("Report", back_populates="job", uselist=False, cascade="all, delete")


class Report(Base):
    """
    Таблица REPORT.
    job_id — одновременно PK и FK (one-to-one с Job).
    metrics — JSON с результатами анализа от DSP-воркера.
    """
    __tablename__ = "report"

    job_id  = Column(Integer, ForeignKey("job.id", ondelete="CASCADE"), primary_key=True)
    id      = Column(Integer, autoincrement=True, nullable=False)
    metrics = Column(JSON, nullable=False, default=dict)

    job = relationship("Job", back_populates="report")


class JobStatusCache(Base):
    """
    Таблица JOB_STATUS_CACHE.
    Дублирует Redis — используется для хранения итогового статуса.
    cache_key формат: "job_status:{job_id}"
    """
    __tablename__ = "job_status_cache"

    cache_key = Column(String(100), primary_key=True)
    status    = Column(String(20),  nullable=False)


class JobProgressCache(Base):
    """
    Таблица JOB_PROGRESS_CACHE.
    Прогресс от 0 до 100.
    cache_key формат: "job_progress:{job_id}"
    """
    __tablename__ = "job_progress_cache"

    cache_key = Column(String(100), primary_key=True)
    progress  = Column(Integer, nullable=False, default=0)
