import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

from app.database import IS_POSTGRES, SessionLocal
from app.models.db_models import VerificationJobORM

logger = logging.getLogger("veritas.services.job_store")


def normalize_claim(text: str) -> str:
    """
    Normalizes claim text for deterministic hashing and caching:
    lowercases, removes leading/trailing punctuation, collapses whitespace.
    """
    if not text:
        return ""
    t = text.lower().strip()
    # Remove punctuation
    t = re.sub(r"[^\w\s]", "", t)
    # Collapse multiple whitespace characters into single space
    t = re.sub(r"\s+", " ", t).strip()
    return t


def compute_claim_hash(text: str) -> str:
    """Computes a SHA-256 hash of normalized claim text for fast cache lookup."""
    norm = normalize_claim(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class JobStore:
    """
    Persistent Job Repository supporting both PostgreSQL (via SQLAlchemy)
    and SQLite fallback for audit persistence and cross-device sync.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "jobs.db")
        else:
            self.db_path = str(db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create jobs table and indexing if not exists."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    claim_hash TEXT NOT NULL,
                    raw_claim TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    latency_ms REAL,
                    token_count INTEGER DEFAULT 0,
                    cached INTEGER DEFAULT 0,
                    cache_type TEXT,
                    similarity REAL,
                    error TEXT
                );
                """
            )
            # Add columns if upgrading from existing schema
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN cache_type TEXT;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN similarity REAL;")
            except Exception:
                pass

            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_claim_hash ON jobs(claim_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);")
            conn.commit()

    def clear(self) -> None:
        """Clears all jobs from the jobs table (for test isolation)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM jobs;")
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    session.query(VerificationJobORM).delete()
                    session.commit()
            except Exception:
                pass

    def create_job(
        self,
        job_id: str,
        raw_claim: str,
        claim_hash: str,
        status: str = "pending",
        stage: str = "queued",
        user_id: Optional[int] = None,
    ) -> None:
        """Inserts a new verification job row with initial status 'pending'."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, claim_hash, raw_claim, status, stage,
                    created_at, token_count, cached
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0);
                """,
                (job_id, user_id, claim_hash, raw_claim, status, stage, now_ts),
            )
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = VerificationJobORM(
                        job_id=job_id,
                        user_id=user_id,
                        claim_hash=claim_hash,
                        raw_claim=raw_claim,
                        status=status,
                        stage=stage,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(orm_job)
                    session.commit()
            except Exception as exc:
                logger.warning(f"Failed to sync job to PostgreSQL: {exc}")

        logger.info(f"Created job {job_id} in state '{status}' for claim: {raw_claim[:60]}... (user: {user_id})")

    def update_job_stage(
        self,
        job_id: str,
        status: str,
        stage: str,
        error: Optional[str] = None,
    ) -> None:
        """Updates the progress stage and status of an active job."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, stage = ?, error = ?
                WHERE job_id = ?;
                """,
                (status, stage, error, job_id),
            )
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = session.query(VerificationJobORM).filter(VerificationJobORM.job_id == job_id).first()
                    if orm_job:
                        orm_job.status = status
                        orm_job.stage = stage
                        orm_job.error = error
                        session.commit()
            except Exception:
                pass

    def complete_job(
        self,
        job_id: str,
        result_dict: Dict[str, Any],
        latency_ms: float,
        token_count: int,
    ) -> None:
        """Marks a job as completed, storing the full result JSON, latency, and token metrics."""
        now_ts = datetime.now(timezone.utc).isoformat()
        result_json_str = json.dumps(result_dict)
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'completed',
                    stage = 'completed',
                    result_json = ?,
                    completed_at = ?,
                    latency_ms = ?,
                    token_count = ?,
                    error = NULL
                WHERE job_id = ?;
                """,
                (result_json_str, now_ts, latency_ms, token_count, job_id),
            )
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = session.query(VerificationJobORM).filter(VerificationJobORM.job_id == job_id).first()
                    if orm_job:
                        orm_job.status = "completed"
                        orm_job.stage = "completed"
                        orm_job.result_json = result_json_str
                        orm_job.completed_at = datetime.now(timezone.utc)
                        orm_job.latency_ms = latency_ms
                        orm_job.token_count = token_count
                        orm_job.error = None
                        session.commit()
            except Exception as exc:
                logger.warning(f"Failed to sync completed job to PostgreSQL: {exc}")

        logger.info(
            f"Job {job_id} completed successfully in {latency_ms:.1f}ms (tokens: {token_count})."
        )

    def fail_job(self, job_id: str, error_message: str, latency_ms: float = 0.0) -> None:
        """Marks a job as failed with error details."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    stage = 'failed',
                    completed_at = ?,
                    latency_ms = ?,
                    error = ?
                WHERE job_id = ?;
                """,
                (now_ts, latency_ms, error_message, job_id),
            )
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = session.query(VerificationJobORM).filter(VerificationJobORM.job_id == job_id).first()
                    if orm_job:
                        orm_job.status = "failed"
                        orm_job.stage = "failed"
                        orm_job.completed_at = datetime.now(timezone.utc)
                        orm_job.latency_ms = latency_ms
                        orm_job.error = error_message
                        session.commit()
            except Exception:
                pass

        logger.warning(f"Job {job_id} marked failed: {error_message}")

    def find_cached_job(self, claim_hash: str) -> Optional[Dict[str, Any]]:
        """
        Searches for a previously completed job with the exact same claim hash.
        Returns the parsed job dictionary if found, else None.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, user_id, raw_claim, result_json, latency_ms, token_count, completed_at
                FROM jobs
                WHERE claim_hash = ? AND status = 'completed' AND result_json IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1;
                """,
                (claim_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                res_dict = json.loads(row["result_json"])
            except Exception:
                res_dict = None

            return {
                "job_id": row["job_id"],
                "user_id": row["user_id"],
                "raw_claim": row["raw_claim"],
                "result": res_dict,
                "latency_ms": row["latency_ms"],
                "token_count": row["token_count"],
                "completed_at": row["completed_at"],
            }

    def create_cached_job(
        self,
        job_id: str,
        raw_claim: str,
        claim_hash: str,
        cached_result: Dict[str, Any],
        latency_ms: float = 1.5,
        user_id: Optional[int] = None,
        cache_type: str = "exact",
        similarity: Optional[float] = None,
    ) -> None:
        """
        Creates a cache-hit completed job row for demo reproducibility, cross-device sync, and logging.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        result_json_str = json.dumps(cached_result)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, claim_hash, raw_claim, status, stage,
                    result_json, created_at, completed_at, latency_ms,
                    token_count, cached, cache_type, similarity
                ) VALUES (?, ?, ?, ?, 'completed', 'completed', ?, ?, ?, ?, 0, 1, ?, ?);
                """,
                (job_id, user_id, claim_hash, raw_claim, result_json_str, now_ts, now_ts, latency_ms, cache_type, similarity),
            )
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = VerificationJobORM(
                        job_id=job_id,
                        user_id=user_id,
                        claim_hash=claim_hash,
                        raw_claim=raw_claim,
                        status="completed",
                        stage="completed",
                        result_json=result_json_str,
                        created_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        latency_ms=latency_ms,
                        token_count=0,
                        cached=True,
                        cache_type=cache_type,
                        similarity=similarity,
                    )
                    session.add(orm_job)
                    session.commit()
            except Exception:
                pass

        logger.info(f"Served claim '{raw_claim[:50]}...' from {cache_type} cache in {latency_ms:.1f}ms as {job_id}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves job record by ID (from PostgreSQL if active, else SQLite)."""
        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_job = session.query(VerificationJobORM).filter(VerificationJobORM.job_id == job_id).first()
                    if orm_job:
                        res_dict = None
                        if orm_job.result_json:
                            try:
                                res_dict = json.loads(orm_job.result_json)
                            except Exception:
                                res_dict = None
                        return {
                            "job_id": orm_job.job_id,
                            "user_id": orm_job.user_id,
                            "claim": orm_job.raw_claim,
                            "status": orm_job.status,
                            "stage": orm_job.stage,
                            "created_at": orm_job.created_at.isoformat() if orm_job.created_at else None,
                            "completed_at": orm_job.completed_at.isoformat() if orm_job.completed_at else None,
                            "latency_ms": orm_job.latency_ms,
                            "token_count": orm_job.token_count or 0,
                            "cached": bool(orm_job.cached),
                            "cache_type": orm_job.cache_type,
                            "similarity": orm_job.similarity,
                            "result": res_dict,
                            "verdict": res_dict.get("verdict") if isinstance(res_dict, dict) else None,
                            "confidence": res_dict.get("confidence") if isinstance(res_dict, dict) else None,
                            "error": orm_job.error,
                        }
            except Exception as pg_err:
                logger.warning(f"PostgreSQL get_job error ({pg_err}); checking SQLite.")

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, user_id, claim_hash, raw_claim, status, stage,
                       result_json, created_at, completed_at, latency_ms,
                       token_count, cached, cache_type, similarity, error
                FROM jobs
                WHERE job_id = ?;
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            result_dict = None
            if row["result_json"]:
                try:
                    result_dict = json.loads(row["result_json"])
                except Exception:
                    result_dict = None

            keys = row.keys()
            verdict = result_dict.get("verdict") if isinstance(result_dict, dict) else None
            confidence = result_dict.get("confidence") if isinstance(result_dict, dict) else None

            return {
                "job_id": row["job_id"],
                "user_id": row["user_id"],
                "claim": row["raw_claim"],
                "status": row["status"],
                "stage": row["stage"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "latency_ms": row["latency_ms"],
                "token_count": row["token_count"] or 0,
                "cached": bool(row["cached"]),
                "cache_type": row["cache_type"] if "cache_type" in keys else None,
                "similarity": row["similarity"] if "similarity" in keys else None,
                "result": result_dict,
                "verdict": verdict,
                "confidence": confidence,
                "error": row["error"],
            }

    def list_user_jobs(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves completed audit history for an authenticated user."""
        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_jobs = (
                        session.query(VerificationJobORM)
                        .filter(
                            VerificationJobORM.user_id == user_id,
                            VerificationJobORM.status == "completed",
                            VerificationJobORM.result_json.isnot(None),
                        )
                        .order_by(VerificationJobORM.created_at.desc())
                        .limit(limit)
                        .all()
                    )
                    if orm_jobs:
                        output = []
                        for job in orm_jobs:
                            try:
                                res = json.loads(job.result_json) if job.result_json else None
                            except Exception:
                                res = None
                            verdict = res.get("verdict") if isinstance(res, dict) else None
                            confidence = res.get("confidence") if isinstance(res, dict) else None
                            output.append({
                                "job_id": job.job_id,
                                "user_id": job.user_id,
                                "claim": job.raw_claim,
                                "status": job.status,
                                "stage": job.stage,
                                "result": res,
                                "verdict": verdict,
                                "confidence": confidence,
                                "created_at": job.created_at.isoformat() if job.created_at else None,
                                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                                "latency_ms": job.latency_ms,
                                "token_count": job.token_count or 0,
                                "cached": bool(job.cached),
                                "cache_type": job.cache_type,
                                "similarity": job.similarity,
                            })
                        return output
            except Exception as pg_err:
                logger.warning(f"PostgreSQL list_user_jobs error ({pg_err}); checking SQLite.")

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, user_id, raw_claim, status, stage, result_json,
                       created_at, completed_at, latency_ms, token_count, cached, cache_type, similarity
                FROM jobs
                WHERE user_id = ? AND status = 'completed' AND result_json IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
            output = []
            for row in rows:
                try:
                    res = json.loads(row["result_json"]) if row["result_json"] else None
                except Exception:
                    res = None
                verdict = res.get("verdict") if isinstance(res, dict) else None
                confidence = res.get("confidence") if isinstance(res, dict) else None
                keys = row.keys()
                output.append({
                    "job_id": row["job_id"],
                    "user_id": row["user_id"],
                    "claim": row["raw_claim"],
                    "status": row["status"],
                    "stage": row["stage"],
                    "result": res,
                    "verdict": verdict,
                    "confidence": confidence,
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "latency_ms": row["latency_ms"],
                    "token_count": row["token_count"] or 0,
                    "cached": bool(row["cached"]),
                    "cache_type": row["cache_type"] if "cache_type" in keys else None,
                    "similarity": row["similarity"] if "similarity" in keys else None,
                })
            return output

    def list_recent_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves recent completed jobs for anonymous/guest sessions."""
        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    orm_jobs = (
                        session.query(VerificationJobORM)
                        .filter(
                            VerificationJobORM.status == "completed",
                            VerificationJobORM.result_json.isnot(None),
                        )
                        .order_by(VerificationJobORM.created_at.desc())
                        .limit(limit)
                        .all()
                    )
                    if orm_jobs:
                        output = []
                        for job in orm_jobs:
                            try:
                                res = json.loads(job.result_json) if job.result_json else None
                            except Exception:
                                res = None
                            verdict = res.get("verdict") if isinstance(res, dict) else None
                            confidence = res.get("confidence") if isinstance(res, dict) else None
                            output.append({
                                "job_id": job.job_id,
                                "user_id": job.user_id,
                                "claim": job.raw_claim,
                                "status": job.status,
                                "stage": job.stage,
                                "result": res,
                                "verdict": verdict,
                                "confidence": confidence,
                                "created_at": job.created_at.isoformat() if job.created_at else None,
                                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                                "latency_ms": job.latency_ms,
                                "token_count": job.token_count or 0,
                                "cached": bool(job.cached),
                                "cache_type": job.cache_type,
                                "similarity": job.similarity,
                            })
                        return output
            except Exception as pg_err:
                logger.warning(f"PostgreSQL list_recent_jobs error ({pg_err}); checking SQLite.")

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, user_id, raw_claim, status, stage, result_json,
                       created_at, completed_at, latency_ms, token_count, cached, cache_type, similarity
                FROM jobs
                WHERE status = 'completed' AND result_json IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            output = []
            for row in rows:
                try:
                    res = json.loads(row["result_json"]) if row["result_json"] else None
                except Exception:
                    res = None
                verdict = res.get("verdict") if isinstance(res, dict) else None
                confidence = res.get("confidence") if isinstance(res, dict) else None
                keys = row.keys()
                output.append({
                    "job_id": row["job_id"],
                    "user_id": row["user_id"],
                    "claim": row["raw_claim"],
                    "status": row["status"],
                    "stage": row["stage"],
                    "result": res,
                    "verdict": verdict,
                    "confidence": confidence,
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "latency_ms": row["latency_ms"],
                    "token_count": row["token_count"] or 0,
                    "cached": bool(row["cached"]),
                    "cache_type": row["cache_type"] if "cache_type" in keys else None,
                    "similarity": row["similarity"] if "similarity" in keys else None,
                })
            return output

    def assign_jobs_to_user(self, job_ids: List[str], user_id: int) -> int:
        """Assigns unauthenticated/guest audit jobs to an authenticated user upon login."""
        if not job_ids or not user_id:
            return 0

        updated_count = 0
        with self._get_connection() as conn:
            for jid in job_ids:
                if not jid or not isinstance(jid, str):
                    continue
                cursor = conn.execute(
                    "UPDATE jobs SET user_id = ? WHERE job_id = ? AND (user_id IS NULL OR user_id = ?);",
                    (user_id, jid.strip(), user_id),
                )
                updated_count += cursor.rowcount
            conn.commit()

        if IS_POSTGRES:
            try:
                with SessionLocal() as session:
                    for jid in job_ids:
                        if not jid or not isinstance(jid, str):
                            continue
                        orm_job = session.query(VerificationJobORM).filter(
                            VerificationJobORM.job_id == jid.strip()
                        ).first()
                        if orm_job and (orm_job.user_id is None or orm_job.user_id == user_id):
                            orm_job.user_id = user_id
                    session.commit()
            except Exception as exc:
                logger.warning(f"Failed to assign jobs to user in PostgreSQL: {exc}")

        logger.info(f"Assigned {updated_count} guest audit jobs to user_id={user_id}")
        return updated_count

    def delete_job(self, job_id: str, user_id: Optional[int] = None) -> bool:
        """Deletes a job record, optionally verifying user ownership."""
        with self._get_connection() as conn:
            if user_id is not None:
                cursor = conn.execute(
                    "DELETE FROM jobs WHERE job_id = ? AND user_id = ?;",
                    (job_id, user_id),
                )
            else:
                cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?;", (job_id,))
            conn.commit()
            deleted = cursor.rowcount > 0

        if IS_POSTGRES and deleted:
            try:
                with SessionLocal() as session:
                    q = session.query(VerificationJobORM).filter(VerificationJobORM.job_id == job_id)
                    if user_id is not None:
                        q = q.filter(VerificationJobORM.user_id == user_id)
                    q.delete()
                    session.commit()
            except Exception:
                pass

        return deleted


# Singleton job store instance
_global_job_store: Optional[JobStore] = None


def get_job_store(db_path: Optional[Union[str, Path]] = None) -> JobStore:
    """Returns or initializes the singleton JobStore."""
    global _global_job_store
    if _global_job_store is None:
        _global_job_store = JobStore(db_path=db_path)
    return _global_job_store
