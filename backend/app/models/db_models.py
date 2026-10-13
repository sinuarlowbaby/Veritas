import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base, IS_POSTGRES, PGVECTOR_AVAILABLE

if IS_POSTGRES and PGVECTOR_AVAILABLE:
    from pgvector.sqlalchemy import Vector
    VectorType = Vector(1536)
else:
    VectorType = Text  # Fallback to Text for storing JSON-encoded float vectors in SQLite


class UserORM(Base):
    """
    User accounts for authentication and cross-device audit persistence.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    jobs = relationship("VerificationJobORM", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("FeedbackORM", back_populates="user")


class VerificationJobORM(Base):
    """
    Verification jobs / audits, optionally associated with an authenticated user.
    """
    __tablename__ = "verification_jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    claim_hash = Column(String(64), index=True, nullable=False)
    raw_claim = Column(Text, nullable=False)
    status = Column(String(32), index=True, nullable=False, default="pending")
    stage = Column(String(32), nullable=True, default="queued")
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    latency_ms = Column(Float, nullable=True)
    token_count = Column(Integer, default=0)
    cached = Column(Boolean, default=False)
    cache_type = Column(String(32), nullable=True)  # 'exact' or 'semantic'
    similarity = Column(Float, nullable=True)  # similarity score for semantic cache hits
    error = Column(Text, nullable=True)

    # Relationships
    user = relationship("UserORM", back_populates="jobs")
    feedbacks = relationship("FeedbackORM", back_populates="job", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert ORM record to dictionary."""
        res_data = None
        if self.result_json:
            try:
                res_data = json.loads(self.result_json)
            except Exception:
                res_data = None

        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "claim": self.raw_claim,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "latency_ms": self.latency_ms,
            "token_count": self.token_count or 0,
            "cached": bool(self.cached),
            "cache_type": self.cache_type,
            "similarity": self.similarity,
            "result": res_data,
            "error": self.error,
        }


class SemanticCacheORM(Base):
    """
    Semantic cache table storing claim embeddings and pre-computed verdicts.
    Enables fast sub-100ms retrieval of conceptually identical claims.
    """
    __tablename__ = "semantic_cache"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    claim_text = Column(Text, nullable=False)
    claim_hash = Column(String(64), index=True, nullable=False)
    embedding = Column(VectorType, nullable=False)
    result_json = Column(Text, nullable=False)
    verdict = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def get_embedding(self) -> List[float]:
        """Safely retrieve embedding as a list of floats."""
        if isinstance(self.embedding, list):
            return self.embedding
        if isinstance(self.embedding, str):
            try:
                return json.loads(self.embedding)
            except Exception:
                return []
        return list(self.embedding) if self.embedding is not None else []


class CuratedFactCheckORM(Base):
    """
    Canonical fact-check corpus for RAG retrieval in PostgreSQL + pgvector (or fallback).
    """
    __tablename__ = "curated_fact_checks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(512), nullable=False)
    source_url = Column(String(1024), nullable=False)
    source_name = Column(String(128), nullable=False)
    verdict = Column(String(64), nullable=False)
    publish_date = Column(String(32), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(VectorType, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class FeedbackORM(Base):
    """
    User feedback on audit accuracy.
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    job_id = Column(String(64), ForeignKey("verification_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating = Column(String(32), nullable=False)  # 'thumbs_up' or 'thumbs_down'
    verdict = Column(String(64), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    job = relationship("VerificationJobORM", back_populates="feedbacks")
    user = relationship("UserORM", back_populates="feedbacks")
