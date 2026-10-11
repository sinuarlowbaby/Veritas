import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict


from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("veritas")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Initializing Veritas API services...")
    # Preload NLI Cross-Encoder model once at startup (inside lifespan, not per request)
    try:
        from app.services.nli_verifier import get_nli_verifier
        verifier = get_nli_verifier()
        verifier.load_model()
        app.state.nli_verifier = verifier
        logger.info("NLI Verifier cross-encoder model loaded and ready in lifespan.")
    except Exception as exc:
        logger.warning(f"NLI model preloading in lifespan encountered notice: {exc}")

    yield
    # Cleanup resources on shutdown
    logger.info("Shutting down Veritas API...")


app = FastAPI(
    title="Veritas API",
    description="A Multi-Agent Debate System for Fake News Verification with Web Search",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.schemas import (
    DecomposeRequest,
    DecomposeResponse,
    SearchRequest,
    SearchResponse,
    BatchQuestionsRequest,
    BatchQuestionsResponse,
    NLIRequest,
    NLIResponse,
    JudgeVerdictRequest,
    JudgeVerdictResponse,
)
from app.agents.decomposer import decompose_claim
from app.agents.judge import judge_evaluate_claim
from app.tools.web_search import search_web, WebSearchError
from app.tools.rag_retriever import retrieve_curated_evidence
from app.services.nli_verifier import get_nli_verifier

@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify service availability."""
    return {
        "status": "ok",
        "service": "veritas-api",
        "version": "0.1.0",
    }


@app.post(
    "/api/decompose",
    response_model=DecomposeResponse,
    tags=["Decomposer"],
    summary="Decompose composite claim into atomic sub-claims",
)
async def decompose_endpoint(payload: DecomposeRequest) -> DecomposeResponse:
    """
    Takes raw user input (headline, claim, or URL text) and returns a list of
    atomic, independently checkable sub-claims with Langfuse tracing.
    """
    return await decompose_claim(payload.text)


@app.post(
    "/api/search",
    response_model=SearchResponse,
    tags=["Web Search"],
    summary="Search web for a question or claim",
    description="Submits a question to the web search fallback chain (TinyFish -> Tavily -> DuckDuckGo) with auto-retry.",
)
async def search_question_endpoint(payload: SearchRequest) -> SearchResponse:
    """
    Accepts a question or search query, invokes the web search tool across
    the fallback chain, and returns structured search results with extracted page content.
    """
    try:
        resolved_query = payload.resolved_query()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        results = await search_web(query=resolved_query, max_results=payload.max_results)
        provider_used = results[0].source if results else "none"
        return SearchResponse(
            question=resolved_query,
            provider_used=provider_used,
            total_results=len(results),
            results=results,
        )
    except WebSearchError as exc:
        logger.error(f"Web search error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All search providers failed: {str(exc)}",
        )
    except Exception as exc:
        logger.exception(f"Unexpected search error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing search: {str(exc)}",
        )


@app.get(
    "/api/search",
    response_model=SearchResponse,
    tags=["Web Search"],
    summary="Search web for a question (GET)",
    description="Convenient GET endpoint for quick queries directly in browser or Swagger UI.",
)
async def search_question_get_endpoint(
    question: str = Query(..., min_length=2, description="The question or search query"),
    max_results: int = Query(default=5, ge=1, le=20, description="Max results to return"),
) -> SearchResponse:
    """
    Convenient GET endpoint to search for questions and inspect results directly in FastAPI Swagger UI.
    """
    return await search_question_endpoint(SearchRequest(question=question, max_results=max_results))


@app.post(
    "/api/search/batch",
    response_model=BatchQuestionsResponse,
    tags=["Web Search"],
    summary="Batch search multiple questions",
    description="Searches multiple questions concurrently using the web search fallback chain.",
)
async def batch_search_questions_endpoint(payload: BatchQuestionsRequest) -> BatchQuestionsResponse:
    """
    Searches multiple questions concurrently and aggregates the results.
    """
    async def _safe_search(q: str) -> SearchResponse:
        try:
            results = await search_web(query=q, max_results=payload.max_results)
            provider_used = results[0].source if results else "none"
            return SearchResponse(
                question=q,
                provider_used=provider_used,
                total_results=len(results),
                results=results,
            )
        except Exception as err:
            return SearchResponse(
                question=q,
                provider_used="failed",
                total_results=0,
                results=[],
            )

    responses = await asyncio.gather(*[_safe_search(q) for q in payload.questions])
    return BatchQuestionsResponse(
        total_questions=len(payload.questions),
        responses=responses,
    )


@app.post(
    "/api/rag",
    response_model=SearchResponse,
    tags=["Curated Fact RAG"],
    summary="Retrieve curated fact-check evidence for a sub-claim",
    description="Embeds query and searches the curated fact-check corpus (pgvector / local store) for ground truth.",
)
async def rag_retrieve_endpoint(payload: SearchRequest) -> SearchResponse:
    """
    Queries the curated fact-check vector store and returns structured evidence chunks with verdicts.
    """
    try:
        resolved_query = payload.resolved_query()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        results = await retrieve_curated_evidence(query=resolved_query, top_k=payload.max_results)
        provider_used = results[0].source if results else "curated_rag:none"
        return SearchResponse(
            question=resolved_query,
            provider_used=provider_used,
            total_results=len(results),
            results=results,
        )
    except Exception as exc:
        logger.exception(f"Unexpected RAG retrieval error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing RAG retrieval: {str(exc)}",
        )


@app.get(
    "/api/rag",
    response_model=SearchResponse,
    tags=["Curated Fact RAG"],
    summary="Retrieve curated fact-check evidence (GET)",
    description="Convenient GET endpoint to test RAG retrieval directly in Swagger UI.",
)
async def rag_retrieve_get_endpoint(
    question: str = Query(..., min_length=2, description="The sub-claim or query"),
    max_results: int = Query(default=5, ge=1, le=20, description="Max chunks to return"),
) -> SearchResponse:
    return await rag_retrieve_endpoint(SearchRequest(question=question, max_results=max_results))


@app.post(
    "/api/nli/verify",
    response_model=NLIResponse,
    tags=["NLI Verifier"],
    summary="Deterministic NLI verification for (sub_claim, quote) pairs",
    description="Labels (sub_claim, quote) pairs into SUPPORTS, REFUTES, or NEUTRAL with confidence scores.",
)
async def nli_verify_endpoint(payload: NLIRequest) -> NLIResponse:
    verifier = get_nli_verifier()
    pairs = [(p.get("sub_claim", ""), p.get("quote", "")) for p in payload.pairs]
    results = await verifier.apredict_pairs(pairs)
    return NLIResponse(total_pairs=len(results), results=results)


@app.post(
    "/api/judge",
    response_model=JudgeVerdictResponse,
    tags=["Judge Agent"],
    summary="Evaluate claim verdict deterministically with LLM explanation",
    description="Scores evidence per tier weight and recency decay, aggregates sub-claims, triggers abstention when evidence is thin, and produces a 3-5 sentence explanation citing quotes.",
)
async def judge_endpoint(payload: JudgeVerdictRequest) -> JudgeVerdictResponse:
    return await judge_evaluate_claim(
        raw_claim=payload.raw_claim,
        sub_claims=payload.sub_claims,
        evidence_items=payload.evidence,
        generate_explanation=payload.generate_explanation,
    )


# ---------------------------------------------------------------------------
# End-to-End Verification Pipeline & Async Job System
# ---------------------------------------------------------------------------
import uuid
from datetime import datetime, timezone
from app.models.schemas import VerifyClaimRequest, VerificationJobResponse
from app.agents.graph import run_verification_pipeline

# In-memory job repository for asynchronous verification tasks
verification_jobs: Dict[str, VerificationJobResponse] = {}


async def _execute_verification_job(job_id: str, claim_text: str, generate_explanation: bool) -> None:
    """Background worker executing the complete Veritas multi-agent verification pipeline."""
    try:
        def _on_stage(stage_name: str) -> None:
            if job_id in verification_jobs:
                verification_jobs[job_id].stage = stage_name

        if job_id in verification_jobs:
            verification_jobs[job_id].status = "processing"
            verification_jobs[job_id].stage = "decomposing"

        result = await run_verification_pipeline(
            raw_claim=claim_text,
            status_callback=_on_stage,
            generate_explanation=generate_explanation,
        )

        if job_id in verification_jobs:
            verification_jobs[job_id].status = "completed"
            verification_jobs[job_id].stage = "completed"
            verification_jobs[job_id].result = result
            verification_jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"Verification job {job_id} successfully completed with verdict: {result.overall_verdict}")

    except Exception as exc:
        logger.exception(f"Verification job {job_id} failed: {exc}")
        if job_id in verification_jobs:
            verification_jobs[job_id].status = "failed"
            verification_jobs[job_id].stage = "failed"
            verification_jobs[job_id].error = str(exc)
            verification_jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()


@app.post(
    "/api/verify",
    response_model=VerificationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Verification Pipeline"],
    summary="Enqueue asynchronous claim verification job",
    description="Submits a headline/claim to the end-to-end multi-agent verification pipeline (Decomposer -> Proponent/Skeptic -> Sanitizer -> NLI Verifier -> Judge). Returns job_id for status polling.",
)
async def create_verification_job(payload: VerifyClaimRequest) -> VerificationJobResponse:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now_ts = datetime.now(timezone.utc).isoformat()

    job_entry = VerificationJobResponse(
        job_id=job_id,
        status="queued",
        stage="queued",
        created_at=now_ts,
    )
    verification_jobs[job_id] = job_entry

    # Launch background task
    asyncio.create_task(
        _execute_verification_job(
            job_id=job_id,
            claim_text=payload.text,
            generate_explanation=payload.generate_explanation,
        )
    )

    logger.info(f"Created verification job {job_id} for claim: {payload.text[:60]}...")
    return job_entry


@app.get(
    "/api/verify/{job_id}",
    response_model=VerificationJobResponse,
    tags=["Verification Pipeline"],
    summary="Poll verification job status and results",
    description="Polls current status ('queued', 'processing', 'completed', 'failed') and retrieves complete audit response once finished.",
)
async def get_verification_job(job_id: str) -> VerificationJobResponse:
    if job_id not in verification_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification job '{job_id}' not found.",
        )
    return verification_jobs[job_id]


@app.post(
    "/api/verify/sync",
    response_model=JudgeVerdictResponse,
    tags=["Verification Pipeline"],
    summary="Synchronous end-to-end claim verification",
    description="Directly executes full pipeline and blocks until final verdict is computed.",
)
async def verify_claim_sync(payload: VerifyClaimRequest) -> JudgeVerdictResponse:
    try:
        return await run_verification_pipeline(
            raw_claim=payload.text,
            generate_explanation=payload.generate_explanation,
        )
    except Exception as exc:
        logger.exception(f"Synchronous verification error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing verification pipeline: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

