from datetime import datetime, timezone
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class FeedbackStore:
    """Persistent SQLite store for user feedback on claim verification verdicts."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            backend_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = backend_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "feedback.db")
        else:
            self.db_path = db_path

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    comment TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_job ON feedback(job_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);")
            conn.commit()

    def clear(self) -> None:
        """Clears all feedback records (used in test isolation)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM feedback;")
            conn.commit()

    def add_feedback(
        self,
        job_id: str,
        rating: str,
        verdict: str = "",
        comment: str = "",
    ) -> Dict[str, Any]:
        """Inserts a user feedback record (thumbs_up / thumbs_down with optional comment)."""
        record_id = f"fb_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        clean_rating = "thumbs_down" if "down" in rating.lower() else "thumbs_up"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO feedback (id, job_id, rating, verdict, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (record_id, job_id, clean_rating, verdict, comment.strip(), created_at),
            )
            conn.commit()

        return {
            "id": record_id,
            "job_id": job_id,
            "rating": clean_rating,
            "verdict": verdict,
            "comment": comment.strip(),
            "created_at": created_at,
        }

    def list_feedback(
        self,
        rating: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists submitted feedback records with optional rating filter."""
        query = "SELECT * FROM feedback"
        params: List[Any] = []

        if rating:
            clean_rating = "thumbs_down" if "down" in rating.lower() else "thumbs_up"
            query += " WHERE rating = ?"
            params.append(clean_rating)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "job_id": row["job_id"],
                "rating": row["rating"],
                "verdict": row["verdict"],
                "comment": row["comment"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_feedback_by_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Retrieves all feedback items associated with a given job_id."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM feedback WHERE job_id = ? ORDER BY created_at DESC",
                (job_id,),
            )
            rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "job_id": row["job_id"],
                "rating": row["rating"],
                "verdict": row["verdict"],
                "comment": row["comment"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


_global_feedback_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    global _global_feedback_store
    if _global_feedback_store is None:
        _global_feedback_store = FeedbackStore()
    return _global_feedback_store
