import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from app.models.schemas import EvidenceItem

logger = logging.getLogger("veritas.services.evidence_store")


class EvidenceStore:
    """
    Evidence Store interface for Veritas.
    
    Persists structured evidence rows:
      evidence_id, sub_claim_id, sub_claim, quote, source_url, domain,
      domain_tier, publish_date, retrieved_date, nli_label, nli_confidence,
      retrieved_by, curated, nli_scores
    
    Provides persistent SQLite storage (with in-memory capability for testing)
    ensuring that the Judge agent and evaluation metrics can read pre-computed
    NLI labels and confidence scores directly.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "evidence.db")
        else:
            self.db_path = str(db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the evidence table schema if it does not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    sub_claim_id TEXT NOT NULL,
                    sub_claim TEXT,
                    quote TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    domain TEXT,
                    domain_tier INTEGER DEFAULT 2,
                    publish_date TEXT,
                    retrieved_date TEXT,
                    retrieved_by TEXT DEFAULT 'proponent',
                    curated INTEGER DEFAULT 0,
                    nli_label TEXT,
                    nli_confidence REAL,
                    nli_scores TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sub_claim_id ON evidence(sub_claim_id);"
            )
            conn.commit()

    def add_evidence(self, items: List[EvidenceItem]) -> int:
        """Insert or replace evidence rows into the store."""
        if not items:
            return 0

        with self._get_connection() as conn:
            for item in items:
                ev_id = item.evidence_id or f"ev_{uuid.uuid4().hex[:12]}"
                item.evidence_id = ev_id
                retrieved_ts = item.retrieved_date or datetime.now(timezone.utc).isoformat()
                item.retrieved_date = retrieved_ts
                nli_scores_json = json.dumps(item.nli_scores) if item.nli_scores else None

                conn.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id, sub_claim_id, sub_claim, quote, source_url,
                        domain, domain_tier, publish_date, retrieved_date,
                        retrieved_by, curated, nli_label, nli_confidence, nli_scores
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(evidence_id) DO UPDATE SET
                        nli_label=excluded.nli_label,
                        nli_confidence=excluded.nli_confidence,
                        nli_scores=excluded.nli_scores,
                        sub_claim=excluded.sub_claim;
                    """,
                    (
                        ev_id,
                        item.sub_claim_id,
                        item.sub_claim,
                        item.quote,
                        item.source_url,
                        item.domain or "",
                        item.domain_tier or 2,
                        item.publish_date,
                        retrieved_ts,
                        item.retrieved_by or "proponent",
                        1 if item.curated else 0,
                        item.nli_label,
                        item.nli_confidence,
                        nli_scores_json,
                    ),
                )
            conn.commit()
        return len(items)

    def update_nli_results(self, items: List[EvidenceItem]) -> int:
        """Update nli_label, nli_confidence, and nli_scores on existing evidence rows."""
        if not items:
            return 0

        with self._get_connection() as conn:
            for item in items:
                if not item.evidence_id:
                    continue
                nli_scores_json = json.dumps(item.nli_scores) if item.nli_scores else None
                conn.execute(
                    """
                    UPDATE evidence
                    SET nli_label = ?, nli_confidence = ?, nli_scores = ?, sub_claim = ?
                    WHERE evidence_id = ?;
                    """,
                    (
                        item.nli_label,
                        item.nli_confidence,
                        nli_scores_json,
                        item.sub_claim,
                        item.evidence_id,
                    ),
                )
            conn.commit()
        return len(items)

    def get_by_sub_claim(self, sub_claim_id: str) -> List[EvidenceItem]:
        """Fetch all evidence items for a given sub_claim_id."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM evidence WHERE sub_claim_id = ? ORDER BY nli_confidence DESC;",
                (sub_claim_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_item(row) for row in rows]

    def get_all(self) -> List[EvidenceItem]:
        """Fetch all evidence rows in the table."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM evidence;")
            rows = cursor.fetchall()
            return [self._row_to_item(row) for row in rows]

    def count(self) -> int:
        """Return total row count."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM evidence;")
            return cursor.fetchone()[0]

    def clear(self) -> None:
        """Clear all rows from the table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM evidence;")
            conn.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> EvidenceItem:
        nli_scores = None
        if row["nli_scores"]:
            try:
                nli_scores = json.loads(row["nli_scores"])
            except Exception:
                nli_scores = None

        return EvidenceItem(
            evidence_id=row["evidence_id"],
            sub_claim_id=row["sub_claim_id"],
            sub_claim=row["sub_claim"] or "",
            quote=row["quote"],
            source_url=row["source_url"],
            domain=row["domain"] or "",
            domain_tier=row["domain_tier"],
            publish_date=row["publish_date"],
            retrieved_date=row["retrieved_date"],
            retrieved_by=row["retrieved_by"] or "proponent",
            curated=bool(row["curated"]),
            nli_label=row["nli_label"],
            nli_confidence=row["nli_confidence"],
            nli_scores=nli_scores,
        )


__all__ = ["EvidenceStore"]
