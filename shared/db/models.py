"""
shared/db/models.py
ORM-модели, точно отражающие ERD-схему.
"""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    email    = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)

    jobs = relationship("Job", back_populates="user", cascade="all, delete")


class Job(Base):
    __tablename__ = "job"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    genre   = Column(String(50), nullable=False)
    status  = Column(String(20), nullable=False, default="pending")

    user   = relationship("User", back_populates="jobs")
    report = relationship("Report", back_populates="job", uselist=False, cascade="all, delete")


class Report(Base):
    """
    job_id — одновременно PK и FK (one-to-one с Job).
    Колонка id убрана — job_id уже является первичным ключом,
    дублирующий id был причиной IntegrityError (null violation).
    """
    __tablename__ = "report"

    job_id  = Column(Integer, ForeignKey("job.id", ondelete="CASCADE"), primary_key=True)
    metrics = Column(JSON, nullable=False, default=dict)

    job = relationship("Job", back_populates="report")


class JobStatusCache(Base):
    __tablename__ = "job_status_cache"

    cache_key = Column(String(100), primary_key=True)
    status    = Column(String(20), nullable=False)


class JobProgressCache(Base):
    __tablename__ = "job_progress_cache"

    cache_key = Column(String(100), primary_key=True)
    progress  = Column(Integer, nullable=False, default=0)