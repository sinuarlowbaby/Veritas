import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone

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
    Persistent SQLite job repository for asynchronous verification tasks.
    
    Provides:
      - Job state transitions: pending -> processing -> completed / failed
      - Caching lookups by normalized claim hash
      - Full result JSON persistence for instant, simple read polling
      - Latency and token metrics persistence
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create jobs table and indexing if not exists."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
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
                    error TEXT
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_claim_hash ON jobs(claim_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
            conn.commit()

    def clear(self) -> None:
        """Clears all jobs from the jobs table (for test isolation)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM jobs;")
            conn.commit()


    def create_job(
        self,
        job_id: str,
        raw_claim: str,
        claim_hash: str,
        status: str = "pending",
        stage: str = "queued",
    ) -> None:
        """Inserts a new verification job row with initial status 'pending'."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, claim_hash, raw_claim, status, stage,
                    created_at, token_count, cached
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0);
                """,
                (job_id, claim_hash, raw_claim, status, stage, now_ts),
            )
            conn.commit()
        logger.info(f"Created job {job_id} in state '{status}' for claim: {raw_claim[:60]}...")

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
        logger.warning(f"Job {job_id} marked failed: {error_message}")

    def find_cached_job(self, claim_hash: str) -> Optional[Dict[str, Any]]:
        """
        Searches for a previously completed job with the exact same claim hash.
        Returns the parsed job dictionary if found, else None.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, raw_claim, result_json, latency_ms, token_count, completed_at
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
    ) -> None:
        """
        Creates an instant cache-hit completed job row for demo reproducibility and logging.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        result_json_str = json.dumps(cached_result)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, claim_hash, raw_claim, status, stage,
                    result_json, created_at, completed_at, latency_ms,
                    token_count, cached
                ) VALUES (?, ?, ?, 'completed', 'completed', ?, ?, ?, ?, 0, 1);
                """,
                (job_id, claim_hash, raw_claim, result_json_str, now_ts, now_ts, latency_ms),
            )
            conn.commit()
        logger.info(f"Served claim '{raw_claim[:50]}...' from cache in {latency_ms:.1f}ms as {job_id}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves job record by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, claim_hash, raw_claim, status, stage,
                       result_json, created_at, completed_at, latency_ms,
                       token_count, cached, error
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

            return {
                "job_id": row["job_id"],
                "claim": row["raw_claim"],
                "status": row["status"],
                "stage": row["stage"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "latency_ms": row["latency_ms"],
                "token_count": row["token_count"] or 0,
                "cached": bool(row["cached"]),
                "result": result_dict,
                "error": row["error"],
            }


# Singleton job store instance
_global_job_store: Optional[JobStore] = None


def get_job_store(db_path: Optional[Union[str, Path]] = None) -> JobStore:
    """Returns or initializes the singleton JobStore."""
    global _global_job_store
    if _global_job_store is None:
        _global_job_store = JobStore(db_path=db_path)
    return _global_job_store
