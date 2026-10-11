import asyncio
import logging
import os
from typing import List, Optional

from app.models.schemas import EvidenceItem, SearchResult, SubClaim
from app.services.sanitizer import search_result_to_evidence
from app.tools.rag_retriever import retrieve_curated_evidence
from app.tools.web_search import search_web

logger = logging.getLogger("veritas.skeptic")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for Skeptic Agent.")
else:
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


@observe(name="skeptic_harvest")
async def harvest_skeptic_evidence(
    sub_claim: SubClaim,
    max_rag_results: int = 3,
    max_web_results: int = 3,
) -> List[EvidenceItem]:
    """
    Harvests candidate evidence seeking to refute, challenge, or debunk the sub-claim.
    Queries both the Curated Fact RAG corpus and Live Web Search using adversarial keywords.
    
    Args:
        sub_claim: The atomic sub-claim to gather counter-evidence for.
        max_rag_results: Max chunks from curated RAG.
        max_web_results: Max results from web search.
        
    Returns:
        List of EvidenceItem candidates tagged with retrieved_by='skeptic'.
    """
    logger.info(f"Skeptic harvesting for [{sub_claim.id}]: '{sub_claim.text}'")

    evidence_candidates: List[EvidenceItem] = []

    # 1. Query Curated RAG with debunk-oriented query
    rag_query = f"{sub_claim.text} fact check debunk false"

    async def _query_rag() -> List[SearchResult]:
        try:
            return await retrieve_curated_evidence(
                query=rag_query,
                top_k=max_rag_results,
                min_similarity=0.45,
            )
        except Exception as exc:
            logger.warning(f"Skeptic RAG query failed for [{sub_claim.id}]: {exc}")
            return []

    # 2. Query Live Web Search with adversarial/fact-check query
    web_query = f"{sub_claim.text} fact check"

    async def _query_web() -> List[SearchResult]:
        try:
            return await search_web(
                query=web_query,
                max_results=max_web_results,
            )
        except Exception as exc:
            logger.warning(f"Skeptic Web query failed for [{sub_claim.id}]: {exc}")
            return []

    # Run RAG and Web queries concurrently
    rag_results, web_results = await asyncio.gather(_query_rag(), _query_web())

    # Convert RAG results
    for res in rag_results:
        ev = search_result_to_evidence(
            result=res,
            sub_claim_id=sub_claim.id,
            sub_claim=sub_claim.text,
            retrieved_by="skeptic",
        )
        if ev:
            evidence_candidates.append(ev)

    # Convert Web results
    for res in web_results:
        ev = search_result_to_evidence(
            result=res,
            sub_claim_id=sub_claim.id,
            sub_claim=sub_claim.text,
            retrieved_by="skeptic",
        )
        if ev:
            evidence_candidates.append(ev)

    logger.info(
        f"Skeptic retrieved {len(evidence_candidates)} candidate counter-evidence items for [{sub_claim.id}]"
    )
    return evidence_candidates
