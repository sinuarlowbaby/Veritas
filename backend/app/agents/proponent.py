import asyncio
import logging
import os
from typing import List, Optional

from app.models.schemas import EvidenceItem, SearchResult, SubClaim
from app.services.sanitizer import search_result_to_evidence
from app.tools.rag_retriever import retrieve_curated_evidence
from app.tools.web_search import search_web

logger = logging.getLogger("veritas.proponent")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for Proponent Agent.")
else:
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


@observe(name="proponent_harvest")
async def harvest_proponent_evidence(
    sub_claim: SubClaim,
    max_rag_results: int = 3,
    max_web_results: int = 3,
) -> List[EvidenceItem]:
    """
    Harvests candidate evidence seeking to support or verify the sub-claim.
    Queries both the Curated Fact RAG corpus and Live Web Search using affirmative phrasing.
    
    Args:
        sub_claim: The atomic sub-claim to gather evidence for.
        max_rag_results: Max chunks from curated RAG.
        max_web_results: Max results from web search.
        
    Returns:
        List of EvidenceItem candidates tagged with retrieved_by='proponent'.
    """
    logger.info(f"Proponent harvesting for [{sub_claim.id}]: '{sub_claim.text}'")

    evidence_candidates: List[EvidenceItem] = []

    # 1. Query Curated RAG with direct sub-claim text
    async def _query_rag() -> List[SearchResult]:
        try:
            return await retrieve_curated_evidence(
                query=sub_claim.text,
                top_k=max_rag_results,
                min_similarity=0.45,
            )
        except Exception as exc:
            logger.warning(f"Proponent RAG query failed for [{sub_claim.id}]: {exc}")
            return []

    # 2. Query Live Web Search with affirmative assertion
    async def _query_web() -> List[SearchResult]:
        try:
            return await search_web(
                query=sub_claim.text,
                max_results=max_web_results,
            )
        except Exception as exc:
            logger.warning(f"Proponent Web query failed for [{sub_claim.id}]: {exc}")
            return []

    # Run RAG and Web queries concurrently
    rag_results, web_results = await asyncio.gather(_query_rag(), _query_web())

    # Convert RAG results
    for res in rag_results:
        ev = search_result_to_evidence(
            result=res,
            sub_claim_id=sub_claim.id,
            sub_claim=sub_claim.text,
            retrieved_by="proponent",
        )
        if ev:
            evidence_candidates.append(ev)

    # Convert Web results
    for res in web_results:
        ev = search_result_to_evidence(
            result=res,
            sub_claim_id=sub_claim.id,
            sub_claim=sub_claim.text,
            retrieved_by="proponent",
        )
        if ev:
            evidence_candidates.append(ev)

    logger.info(
        f"Proponent retrieved {len(evidence_candidates)} candidate evidence items for [{sub_claim.id}]"
    )
    return evidence_candidates
