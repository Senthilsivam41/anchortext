"""SQLite ledger for match config, review tasks, and the one charge per image."""

import hashlib
import hmac
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ApiKeyRow(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String, unique=True, index=True)


class MatchConfigRow(Base):
    __tablename__ = "match_configs"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String)
    source_location: Mapped[str] = mapped_column(String)
    caller_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"))


class DetectionRow(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    caller_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"))
    source_id: Mapped[str] = mapped_column(String)
    work_level: Mapped[str] = mapped_column(String)
    image_path: Mapped[str] = mapped_column(String)
    image_width: Mapped[int] = mapped_column()
    image_height: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageChargeRow(Base):
    __tablename__ = "usage_charges"
    __table_args__ = (UniqueConstraint("detection_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"))
    caller_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"))
    work_level: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewTaskRow(Base):
    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"))
    caller_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"))
    status: Mapped[str] = mapped_column(String)


class AnnotationRow(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"))
    review_task_id: Mapped[str | None] = mapped_column(ForeignKey("review_tasks.id"), nullable=True)
    text_raw: Mapped[str] = mapped_column(Text)
    text_normalized: Mapped[str] = mapped_column(Text)
    text_class: Mapped[str] = mapped_column(String)
    polygon_json: Mapped[str] = mapped_column(Text)
    rotation_degrees: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    domain_validation_score: Mapped[float] = mapped_column(Float)
    matched_ref_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    release_state: Mapped[str] = mapped_column(String)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def keys_match(api_key: str, key_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), key_hash)


def make_engine(database_url: str):
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _wal(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
