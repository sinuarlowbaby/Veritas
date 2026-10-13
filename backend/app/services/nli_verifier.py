import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import re
import scipy.special

# Load environment variables
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    from dotenv import load_dotenv
    load_dotenv(backend_env)

from app.models.schemas import EvidenceItem, NLIPairResult
from app.services.evidence_store import EvidenceStore

logger = logging.getLogger("veritas.services.nli_verifier")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for NLI Verifier.")
else:
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    logger.info("Langfuse credentials not set; running NLI Verifier with standard logging.")


# Canonical label mappings from CrossEncoder NLI classes to Veritas schema
ID_TO_LABEL_MAP = {
    0: "REFUTES",    # contradiction
    1: "SUPPORTS",   # entailment
    2: "NEUTRAL",    # neutral
}

# Explicit debunking and fact-checking phrases that denote contradiction/falsification
# of an affirmative claim in journalistic evidence
DEBUNK_QUOTE_PATTERNS = [
    r'\b(?:fake|fabricated|doctored|morphed)\b\s+(?:resignation|letter|claim|news|notice|order|circular|document|video|image|photo|notification|post|tweet|quote)',
    r'\b(?:false|fake|misleading|fabricated|unfounded|baseless)\s+(?:claim|rumor|letter|post|news|report|story)\b',
    r'\b(?:claim|letter|rumor|post|story|news|notification|order)\s+(?:is|was|are|were|has been)\s+(?:found\s+to\s+be\s+)?(?:completely\s+|entirely\s+)?(?:false|fake|untrue|baseless|misleading|fabricated|a hoax)\b',
    r'\b(?:found|confirmed|declared|labeled|rated|called|flagged)\b.*?\b(?:claim|post|letter|video|story|rumor)\b.*?\b(?:false|fake|misleading|fabricated|untrue|a hoax)\b',
    r'\b(?:dismissed|denied|rejected|refuted|busted|debunked|debunks|debunking)\b.*?\b(?:fake|false|rumor|claim|letter|report|allegation|post|story)\b',
    r'\bclarified that\b.*?\b(?:is fake|is false|has not|did not|never|no such)\b',
    r'\b(?:fact\s*check|fact-check|pib\s*fact\s*check)\b.*?\b(?:fake|false|misleading|debunk|hoax|untrue|no\b)',
    r'\b(?:no truth\b|baseless\b|unfounded\b|\bhoax\b|\bmyth\b|\bmisinformation\b)',
    r'\b(?:has not|have not|did not)\s+(?:issued|announced|resigned|stepped down|signed|passed|implemented)\b',
    r'\bno such\s+(?:order|announcement|letter|circular|policy|decision|statement)\b',
]
DEBUNK_RE = re.compile('|'.join(DEBUNK_QUOTE_PATTERNS), re.IGNORECASE)

SUBCLAIM_NEG_PATTERNS = [
    r'\b(?:does not|did not|has not|is not|was not|never|fake|false|hoax|untrue)\b'
]
SUBCLAIM_NEG_RE = re.compile('|'.join(SUBCLAIM_NEG_PATTERNS), re.IGNORECASE)


def is_quote_debunking_claim(quote: str, sub_claim: str) -> bool:
    """
    Detects if a retrieved journalistic quote contains explicit debunking language
    targeting an affirmative sub-claim. Standard Cross-Encoders trained on MNLI
    suffer from a meta-discourse blindspot when quotes contain phrases like
    'dismissed a fake resignation letter claiming X' or 'PIB clarified that X is fake',
    misclassifying them as SUPPORTS due to lexical overlap with the embedded clause.
    """
    if not quote or not sub_claim:
        return False
    # If quote has clear debunking markers and sub-claim is affirmative (does not itself assert a negation)
    return bool(DEBUNK_RE.search(quote)) and not bool(SUBCLAIM_NEG_RE.search(sub_claim))



class NLIVerifier:
    """
    Deterministic Natural Language Inference (NLI) Verifier for Veritas.
    
    Uses a local Cross-Encoder (e.g., cross-encoder/nli-distilroberta-base) to classify
    relationships between atomic sub-claims and retrieved evidence quotes into:
      - SUPPORTS: quote directly verifies / entails the sub-claim
      - REFUTES: quote directly contradicts the sub-claim (dates, numbers, assertions)
      - NEUTRAL: quote is on the topic but does not establish or contradict the assertion
    
    IMPORTANT CONVENTION — LABEL DIRECTION:
      The pair MUST ALWAYS be evaluated as:
        (sub_claim, quote) in that exact order.
      Example:
        ("The government announced the policy in March", "The announcement came in September")
        --> REFUTES
      Locking this convention ensures consistent logical direction across Proponent,
      Skeptic, and Judge agents.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/nli-distilroberta-base",
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device or ("cuda" if self._has_cuda() else "cpu")
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def _has_cuda() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def load_model(self) -> None:
        """
        Load the cross-encoder model into memory once.
        Called once during FastAPI lifespan startup.
        """
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return

            logger.info(
                f"Loading NLI CrossEncoder model '{self.model_name}' on device '{self.device}'..."
            )
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
            )
            logger.info("NLI CrossEncoder model successfully loaded and cached in memory.")

    @property
    def model(self):
        if self._model is None:
            self.load_model()
        return self._model

    def predict_pairs(
        self,
        pairs: List[Tuple[str, str]],
        batch_size: int = 32,
    ) -> List[NLIPairResult]:
        """
        Deterministically classifies a batch of (sub_claim, quote) pairs.
        
        Args:
            pairs: List of (sub_claim, quote) string tuples in that exact order.
            batch_size: Batch size for model inference (default: 32).
            
        Returns:
            List of NLIPairResult with label ('SUPPORTS', 'REFUTES', 'NEUTRAL'),
            confidence score (0.0 to 1.0), and full softmax score distribution.
        """
        if not pairs:
            return []

        # Enforce non-empty string pairs
        valid_pairs: List[Tuple[str, str]] = []
        for sc, q in pairs:
            clean_sc = (sc or "").strip()
            clean_q = (q or "").strip()
            valid_pairs.append((clean_sc, clean_q))

        # In NLI Cross-Encoders (trained on MNLI/SNLI), input order is (Premise, Hypothesis).
        # In fact-checking, the Premise is the retrieved Evidence quote (known source text)
        # and the Hypothesis is the Sub-Claim being verified.
        # (quote, sub_claim) evaluates: "Given the quote, is the claim supported or refuted?"
        model_input_pairs = [(q, sc) for sc, q in valid_pairs]

        # Batched prediction on local model
        raw_scores = self.model.predict(
            model_input_pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        results: List[NLIPairResult] = []
        for i, (sc, q) in enumerate(valid_pairs):
            logits = raw_scores[i]
            probs = scipy.special.softmax(logits)

            scores_dict = {
                "REFUTES": float(probs[0]),
                "SUPPORTS": float(probs[1]),
                "NEUTRAL": float(probs[2]),
            }

            best_idx = int(probs.argmax())
            winning_label = ID_TO_LABEL_MAP[best_idx]
            winning_confidence = float(probs[best_idx])

            # Apply debunking override if journalistic quote directly debunks affirmative claim
            if is_quote_debunking_claim(q, sc) and winning_label != "REFUTES":
                logger.info(
                    f"Debunk override: quote contains explicit refutation/debunk signals for sub-claim '{sc[:45]}...'. "
                    f"Overriding raw NLI label '{winning_label}' to 'REFUTES'."
                )
                winning_label = "REFUTES"
                # Calibrate confidence based on original strength or at least 0.88
                winning_confidence = max(0.88, round(winning_confidence, 4))
                rem = round(1.0 - winning_confidence, 4)
                scores_dict = {
                    "REFUTES": winning_confidence,
                    "SUPPORTS": round(rem * 0.3, 4),
                    "NEUTRAL": round(rem * 0.7, 4),
                }

            results.append(
                NLIPairResult(
                    sub_claim=sc,
                    quote=q,
                    nli_label=winning_label,
                    nli_confidence=round(winning_confidence, 4),
                    scores={k: round(v, 4) for k, v in scores_dict.items()},
                )
            )

        return results

    @observe(name="verify_evidence")
    def verify_evidence(
        self,
        evidence_items: List[EvidenceItem],
        sub_claim_map: Optional[Dict[str, str]] = None,
        store: Optional[EvidenceStore] = None,
        batch_size: int = 32,
    ) -> List[EvidenceItem]:
        """
        Labels all evidence items against their respective sub-claims,
        mutating each EvidenceItem with nli_label, nli_confidence, and nli_scores,
        and optionally persisting directly onto the evidence store table.
        
        Args:
            evidence_items: List of EvidenceItem instances.
            sub_claim_map: Optional dictionary mapping sub_claim_id -> sub_claim text.
            store: Optional EvidenceStore instance to persist labeled rows.
            batch_size: Batch size for model inference (default: 32).
            
        Returns:
            The mutated list of EvidenceItem instances with labels and confidences.
        """
        if not evidence_items:
            return []

        sub_claim_map = sub_claim_map or {}
        pairs: List[Tuple[str, str]] = []

        for item in evidence_items:
            # Resolve sub-claim text
            sc_text = item.sub_claim or sub_claim_map.get(item.sub_claim_id, "")
            item.sub_claim = sc_text
            # ALWAYS (sub_claim, quote) order
            pairs.append((sc_text, item.quote))

        pair_results = self.predict_pairs(pairs, batch_size=batch_size)

        for item, res in zip(evidence_items, pair_results):
            item.nli_label = res.nli_label
            item.nli_confidence = res.nli_confidence
            item.nli_scores = res.scores

        # Persist directly onto evidence table if store provided
        if store is not None:
            store.add_evidence(evidence_items)
            logger.info(
                f"Persisted NLI labels onto {len(evidence_items)} rows in EvidenceStore."
            )

        return evidence_items

    async def apredict_pairs(
        self,
        pairs: List[Tuple[str, str]],
        batch_size: int = 32,
    ) -> List[NLIPairResult]:
        """Async wrapper executing predict_pairs in a worker thread."""
        return await asyncio.to_thread(self.predict_pairs, pairs, batch_size)

    async def averify_evidence(
        self,
        evidence_items: List[EvidenceItem],
        sub_claim_map: Optional[Dict[str, str]] = None,
        store: Optional[EvidenceStore] = None,
        batch_size: int = 32,
    ) -> List[EvidenceItem]:
        """Async wrapper executing verify_evidence in a worker thread."""
        return await asyncio.to_thread(
            self.verify_evidence, evidence_items, sub_claim_map, store, batch_size
        )


# Global singleton instance
_nli_verifier_instance: Optional[NLIVerifier] = None
_instance_lock = threading.Lock()


def get_nli_verifier(
    model_name: str = "cross-encoder/nli-distilroberta-base",
) -> NLIVerifier:
    """Return or initialize the singleton NLIVerifier instance."""
    global _nli_verifier_instance
    if _nli_verifier_instance is None:
        with _instance_lock:
            if _nli_verifier_instance is None:
                _nli_verifier_instance = NLIVerifier(model_name=model_name)
    return _nli_verifier_instance


__all__ = [
    "NLIVerifier",
    "get_nli_verifier",
    "ID_TO_LABEL_MAP",
]
