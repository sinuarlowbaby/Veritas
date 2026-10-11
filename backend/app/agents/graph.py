import asyncio
import logging
import os
from typing import Callable, List, Optional

from app.agents.decomposer import decompose_claim
from app.agents.judge import judge_evaluate_claim
from app.agents.proponent import harvest_proponent_evidence
from app.agents.skeptic import harvest_skeptic_evidence
from app.models.schemas import (
    EvidenceItem,
    JudgeVerdictResponse,
    SubClaim,
)
from app.services.evidence_store import EvidenceStore
from app.services.nli_verifier import get_nli_verifier
from app.services.sanitizer import sanitize_evidence

logger = logging.getLogger("veritas.pipeline")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for Veritas Verification Pipeline.")
else:
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


@observe(name="verify_pipeline")
async def run_verification_pipeline(
    raw_claim: str,
    evidence_store: Optional[EvidenceStore] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    generate_explanation: bool = True,
) -> JudgeVerdictResponse:
    """
    End-to-end multi-agent verification pipeline for Veritas:
      1. Headline In -> Claim Decomposer (atomic sub-claims with Langfuse tracing)
      2. Parallel Adversarial Evidence Harvesting (Proponent + Skeptic across Curated RAG and Web)
      3. Evidence Sanitization (URL validation, domain tiering, quote cleaning, deduplication)
      4. Deterministic NLI Verifier ((sub_claim, quote) -> SUPPORTS / REFUTES / NEUTRAL + confidence)
      5. Deterministic Judge (pure math scoring, aggregation, epistemic abstention, LLM narrative explanation)
      6. Verdict + Confidence + Explanation Out.
      
    Args:
        raw_claim: Original headline, viral message, or composite claim.
        evidence_store: Optional EvidenceStore instance to persist evidence rows.
        status_callback: Optional callback receiving pipeline stage updates.
        generate_explanation: Whether to produce narrative LLM audit explanation.
        
    Returns:
        JudgeVerdictResponse containing complete audit trail and final verdict.
    """
    claim_text = (raw_claim or "").strip()
    if not claim_text:
        raise ValueError("Cannot verify an empty claim.")

    def _update_status(stage: str):
        if status_callback:
            try:
                status_callback(stage)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    logger.info(f"=== Starting Veritas Pipeline for claim: '{claim_text[:80]}...' ===")

    # -----------------------------------------------------------------------
    # Step 1: Decompose Claim
    # -----------------------------------------------------------------------
    _update_status("decomposing")
    logger.info("Step 1: Decomposing claim into atomic sub-claims...")
    decompose_resp = await decompose_claim(claim_text)
    sub_claims: List[SubClaim] = decompose_resp.sub_claims

    if not sub_claims:
        # Fallback if decomposition returned empty
        logger.warning("Decomposer produced no sub-claims; using whole claim as single sub-claim.")
        sub_claims = [SubClaim(id="subclaim_1", text=claim_text, type="general")]

    logger.info(f"Step 1 Complete: {len(sub_claims)} atomic sub-claims extracted.")

    # -----------------------------------------------------------------------
    # Step 2: Parallel Adversarial Retrieval (Proponent & Skeptic)
    # -----------------------------------------------------------------------
    _update_status("harvesting_evidence")
    logger.info("Step 2: Harvesting adversarial evidence across Proponent and Skeptic...")

    async def _harvest_for_subclaim(sc: SubClaim) -> List[EvidenceItem]:
        proponent_task = harvest_proponent_evidence(sc)
        skeptic_task = harvest_skeptic_evidence(sc)
        results = await asyncio.gather(proponent_task, skeptic_task)
        # Flatten results
        return results[0] + results[1]

    subclaim_harvest_tasks = [_harvest_for_subclaim(sc) for sc in sub_claims]
    harvest_results = await asyncio.gather(*subclaim_harvest_tasks)

    all_raw_evidence: List[EvidenceItem] = []
    for items in harvest_results:
        all_raw_evidence.extend(items)

    logger.info(
        f"Step 2 Complete: Harvested {len(all_raw_evidence)} raw evidence candidates across all sub-claims."
    )

    # -----------------------------------------------------------------------
    # Step 3: Evidence Sanitization & Deduplication
    # -----------------------------------------------------------------------
    _update_status("sanitizing")
    logger.info("Step 3: Sanitizing quotes, validating domains, and deduplicating...")
    sanitized_evidence = sanitize_evidence(all_raw_evidence)
    logger.info(
        f"Step 3 Complete: Retained {len(sanitized_evidence)} clean, deduplicated evidence items."
    )

    # -----------------------------------------------------------------------
    # Step 4: Deterministic NLI Verification
    # -----------------------------------------------------------------------
    _update_status("nli_verification")
    logger.info("Step 4: Running deterministic NLI Verifier on (sub_claim, quote) pairs...")
    verifier = get_nli_verifier()
    sub_claim_map = {sc.id: sc.text for sc in sub_claims}

    store = evidence_store or EvidenceStore()
    labeled_evidence = await verifier.averify_evidence(
        evidence_items=sanitized_evidence,
        sub_claim_map=sub_claim_map,
        store=store,
    )
    logger.info(
        f"Step 4 Complete: Labeled {len(labeled_evidence)} evidence items with deterministic NLI."
    )

    # -----------------------------------------------------------------------
    # Step 5: Deterministic Judge & Epistemic Abstention
    # -----------------------------------------------------------------------
    _update_status("judge_evaluating")
    logger.info("Step 5: Invoking Judge Agent (pure math scoring + aggregation + explanation)...")
    verdict_response = await judge_evaluate_claim(
        raw_claim=claim_text,
        sub_claims=sub_claims,
        evidence_items=labeled_evidence,
        generate_explanation=generate_explanation,
    )

    _update_status("completed")
    logger.info(
        f"=== Veritas Pipeline Finished | Verdict: {verdict_response.overall_verdict} "
        f"(Confidence: {verdict_response.overall_confidence:.2f}, Abstained: {verdict_response.is_abstained}) ==="
    )

    return verdict_response
