import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from dotenv import load_dotenv

# Load backend or root environment variables
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

from app.models.schemas import CuratedFactChunk

logger = logging.getLogger("veritas.services.vector_store")

# SQLAlchemy and pgvector imports
try:
    from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, select, text
    from sqlalchemy.orm import declarative_base, sessionmaker
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    logger.warning("SQLAlchemy or pgvector not available; pgvector backend disabled.")

Base = declarative_base() if PGVECTOR_AVAILABLE else object


if PGVECTOR_AVAILABLE:
    class CuratedFactCheckORM(Base):
        """
        SQLAlchemy ORM table definition for curated fact checks in PostgreSQL + pgvector.
        """
        __tablename__ = "curated_fact_checks"

        id = Column(Integer, primary_key=True, autoincrement=True)
        title = Column(String(512), nullable=False)
        source_url = Column(String(1024), nullable=False)
        source_name = Column(String(128), nullable=False)
        verdict = Column(String(64), nullable=False)
        publish_date = Column(String(32), nullable=False)
        chunk_index = Column(Integer, nullable=False, default=0)
        chunk_text = Column(Text, nullable=False)
        embedding = Column(Vector(1536), nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow)


class VectorStore:
    """
    Unified Vector Store interface for Veritas.
    
    Operates in two modes:
    1. PostgreSQL + pgvector: Used when DATABASE_URL is set and reachable.
    2. Local JSON/NumPy vector store: Zero-friction fallback when PostgreSQL is not running,
       ensuring immediate execution and testing with identical similarity search semantics.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        local_data_path: Optional[Union[str, Path]] = None,
        embedding_dim: int = 1536,
    ):
        self.embedding_dim = embedding_dim
        self.db_url = db_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        
        # Local fallback path
        if local_data_path:
            self.local_data_path = Path(local_data_path)
        else:
            self.local_data_path = (
                Path(__file__).resolve().parent.parent.parent / "data" / "curated_facts.json"
            )
        self.local_data_path.parent.mkdir(parents=True, exist_ok=True)

        self.use_pgvector = False
        self.engine = None
        self.SessionLocal = None

        self._init_connection()

    def _init_connection(self) -> None:
        """Attempt to connect to PostgreSQL + pgvector; fall back to local store if unavailable."""
        if self.db_url and PGVECTOR_AVAILABLE:
            try:
                # Convert postgres:// to postgresql:// for SQLAlchemy compatibility
                norm_url = self.db_url
                if norm_url.startswith("postgres://"):
                    norm_url = "postgresql://" + norm_url[len("postgres://"):]

                self.engine = create_engine(norm_url, pool_pre_ping=True)
                with self.engine.connect() as conn:
                    # Enable pgvector extension
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                # Create table
                Base.metadata.create_all(self.engine)
                self.SessionLocal = sessionmaker(bind=self.engine)
                self.use_pgvector = True
                logger.info(f"Connected to pgvector table 'curated_fact_checks' at {self.engine.url.host}")
                return
            except Exception as exc:
                logger.warning(
                    f"PostgreSQL/pgvector connection failed ({exc}). Falling back to local vector store."
                )

        self.use_pgvector = False
        logger.info(f"Using local file-backed vector store at '{self.local_data_path}'")

    def insert_chunks(self, chunks: List[CuratedFactChunk]) -> int:
        """
        Store a batch of fact-check chunks with embeddings and metadata.
        """
        if not chunks:
            return 0

        if self.use_pgvector and self.SessionLocal:
            session = self.SessionLocal()
            try:
                orm_items = [
                    CuratedFactCheckORM(
                        title=chunk.title,
                        source_url=chunk.source_url,
                        source_name=chunk.source_name,
                        verdict=chunk.verdict,
                        publish_date=chunk.publish_date,
                        chunk_index=chunk.chunk_index,
                        chunk_text=chunk.chunk_text,
                        embedding=chunk.embedding,
                    )
                    for chunk in chunks
                ]
                session.add_all(orm_items)
                session.commit()
                logger.info(f"Successfully inserted {len(orm_items)} chunks into pgvector.")
                return len(orm_items)
            except Exception as exc:
                session.rollback()
                logger.error(f"Error inserting chunks into pgvector: {exc}")
                raise
            finally:
                session.close()

        # Local storage fallback
        existing_records = self._load_local_records()
        for chunk in chunks:
            rec = {
                "id": len(existing_records) + 1,
                "title": chunk.title,
                "source_url": chunk.source_url,
                "source_name": chunk.source_name,
                "verdict": chunk.verdict,
                "publish_date": chunk.publish_date,
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.chunk_text,
                "embedding": chunk.embedding,
            }
            existing_records.append(rec)

        self._save_local_records(existing_records)
        logger.info(f"Successfully inserted {len(chunks)} chunks into local vector store.")
        return len(chunks)

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> List[CuratedFactChunk]:
        """
        Perform cosine similarity search against stored chunks.
        """
        if not query_embedding:
            return []

        if self.use_pgvector and self.SessionLocal:
            session = self.SessionLocal()
            try:
                # Cosine distance in pgvector: 1 - cosine_distance = cosine_similarity
                cosine_dist = CuratedFactCheckORM.embedding.cosine_distance(query_embedding)
                stmt = (
                    select(
                        CuratedFactCheckORM,
                        (1.0 - cosine_dist).label("similarity"),
                    )
                    .order_by(cosine_dist)
                    .limit(top_k)
                )
                results = session.execute(stmt).all()

                output: List[CuratedFactChunk] = []
                for row in results:
                    item, similarity = row[0], float(row[1])
                    if similarity >= min_similarity:
                        output.append(
                            CuratedFactChunk(
                                id=str(item.id),
                                title=item.title,
                                source_url=item.source_url,
                                source_name=item.source_name,
                                verdict=item.verdict,
                                publish_date=item.publish_date,
                                chunk_index=item.chunk_index,
                                chunk_text=item.chunk_text,
                                similarity=round(similarity, 4),
                            )
                        )
                return output
            finally:
                session.close()

        # Local cosine similarity search
        records = self._load_local_records()
        if not records:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        scored_records: List[Tuple[float, dict]] = []
        for rec in records:
            emb = rec.get("embedding")
            if not emb:
                continue
            v_vec = np.array(emb, dtype=np.float32)
            v_norm = np.linalg.norm(v_vec)
            if v_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q_vec, v_vec) / (q_norm * v_norm))

            if similarity >= min_similarity:
                scored_records.append((similarity, rec))

        # Sort descending by similarity
        scored_records.sort(key=lambda x: x[0], reverse=True)
        top_records = scored_records[:top_k]

        return [
            CuratedFactChunk(
                id=str(r.get("id")),
                title=r.get("title", ""),
                source_url=r.get("source_url", ""),
                source_name=r.get("source_name", ""),
                verdict=r.get("verdict", ""),
                publish_date=r.get("publish_date", ""),
                chunk_index=r.get("chunk_index", 0),
                chunk_text=r.get("chunk_text", ""),
                similarity=round(score, 4),
            )
            for score, r in top_records
        ]

    def count(self) -> int:
        """Return the number of stored chunks."""
        if self.use_pgvector and self.SessionLocal:
            session = self.SessionLocal()
            try:
                return session.query(CuratedFactCheckORM).count()
            finally:
                session.close()
        return len(self._load_local_records())

    def clear(self) -> None:
        """Clear all stored chunks."""
        if self.use_pgvector and self.SessionLocal:
            session = self.SessionLocal()
            try:
                session.query(CuratedFactCheckORM).delete()
                session.commit()
            finally:
                session.close()
        if self.local_data_path.exists():
            self.local_data_path.unlink()

    def _load_local_records(self) -> List[dict]:
        if not self.local_data_path.exists():
            return []
        try:
            with open(self.local_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_local_records(self, records: List[dict]) -> None:
        with open(self.local_data_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
