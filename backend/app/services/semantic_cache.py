import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import IS_POSTGRES, PGVECTOR_AVAILABLE, SessionLocal
from app.models.db_models import SemanticCacheORM
from app.services.job_store import compute_claim_hash, normalize_claim

logger = logging.getLogger("veritas.services.semantic_cache")

DEFAULT_SIMILARITY_THRESHOLD = 0.88


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two float vectors using NumPy."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SemanticCache:
    """
    Semantic Caching service for claim verification.
    
    Checks if a newly submitted claim has high cosine similarity (>= 0.88)
    to an already audited claim in PostgreSQL + pgvector (or fallback SQLite).
    If matched, returns the cached audit result in sub-100ms.
    """

    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.similarity_threshold = similarity_threshold

    def find_match(
        self,
        claim_text: str,
        claim_embedding: List[float],
        threshold: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> Optional[Tuple[Dict[str, Any], float, str]]:
        """
        Search for a semantically matching claim.
        
        Returns:
            Tuple of (result_dict, similarity_score, matched_claim_text) if found, else None.
        """
        thresh = threshold or self.similarity_threshold
        session = db or SessionLocal()
        should_close = db is None

        try:
            # 1. PostgreSQL + pgvector accelerated search
            if IS_POSTGRES and PGVECTOR_AVAILABLE:
                try:
                    # pgvector cosine distance: 1 - (embedding <=> :vec) = cosine similarity
                    vec_str = "[" + ",".join(str(x) for x in claim_embedding) + "]"
                    query = text("""
                        SELECT claim_text, result_json, 1 - (embedding <=> :vec) AS similarity
                        FROM semantic_cache
                        ORDER BY embedding <=> :vec
                        LIMIT 1;
                    """)
                    row = session.execute(query, {"vec": vec_str}).fetchone()
                    if row and row[2] is not None and float(row[2]) >= thresh:
                        similarity = float(row[2])
                        matched_claim = row[0]
                        res_data = json.loads(row[1])
                        logger.info(
                            f"⚡ SEMANTIC CACHE HIT (PostgreSQL pgvector) | Similarity: {similarity:.4f} >= {thresh} "
                            f"| Query: '{claim_text[:50]}' matched '{matched_claim[:50]}'"
                        )
                        return res_data, similarity, matched_claim
                except Exception as pg_err:
                    logger.warning(f"pgvector query error ({pg_err}); checking via fallback.")

            # 2. SQLite / local fallback: query all cached embeddings and compute cosine similarity
            entries = session.query(SemanticCacheORM).all()
            if not entries:
                return None

            best_match = None
            best_sim = -1.0
            best_claim = ""

            for entry in entries:
                entry_emb = entry.get_embedding()
                if not entry_emb:
                    continue
                sim = cosine_similarity(claim_embedding, entry_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_match = entry
                    best_claim = entry.claim_text

            if best_match and best_sim >= thresh:
                try:
                    res_data = json.loads(best_match.result_json)
                    logger.info(
                        f"⚡ SEMANTIC CACHE HIT (Local/Fallback) | Similarity: {best_sim:.4f} >= {thresh} "
                        f"| Query: '{claim_text[:50]}' matched '{best_claim[:50]}'"
                    )
                    return res_data, best_sim, best_claim
                except Exception as parse_err:
                    logger.warning(f"Failed to parse cached result_json: {parse_err}")

            return None
        finally:
            if should_close:
                session.close()

    def store(
        self,
        claim_text: str,
        result_dict: Dict[str, Any],
        claim_embedding: List[float],
        verdict: Optional[str] = None,
        confidence: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> None:
        """
        Store a verified claim and its embedding in the semantic cache.
        """
        if not claim_embedding or not claim_text:
            return

        session = db or SessionLocal()
        should_close = db is None

        try:
            claim_hash = compute_claim_hash(claim_text)
            norm = normalize_claim(claim_text)

            # Check if this exact claim already exists in semantic cache
            existing = session.query(SemanticCacheORM).filter(SemanticCacheORM.claim_hash == claim_hash).first()
            if existing:
                existing.result_json = json.dumps(result_dict)
                existing.verdict = verdict or result_dict.get("verdict")
                existing.confidence = confidence or result_dict.get("confidence")
                if IS_POSTGRES and PGVECTOR_AVAILABLE:
                    existing.embedding = claim_embedding
                else:
                    existing.embedding = json.dumps(claim_embedding)
                session.commit()
                return

            if IS_POSTGRES and PGVECTOR_AVAILABLE:
                stored_emb = claim_embedding
            else:
                stored_emb = json.dumps(claim_embedding)

            entry = SemanticCacheORM(
                claim_text=norm,
                claim_hash=claim_hash,
                embedding=stored_emb,
                result_json=json.dumps(result_dict),
                verdict=verdict or result_dict.get("verdict"),
                confidence=confidence or result_dict.get("confidence"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(entry)
            session.commit()
            logger.info(f"Stored claim in semantic cache: '{claim_text[:60]}...'")
        except Exception as exc:
            session.rollback()
            logger.warning(f"Failed to store entry in semantic cache: {exc}")
        finally:
            if should_close:
                session.close()


_global_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Singleton getter for SemanticCache."""
    global _global_semantic_cache
    if _global_semantic_cache is None:
        _global_semantic_cache = SemanticCache()
    return _global_semantic_cache
