import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional


from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
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
    # Initialize PostgreSQL or fallback SQLite tables
    try:
        from app.database import init_db
        init_db()
        logger.info("Database tables initialized in lifespan.")
    except Exception as exc:
        logger.warning(f"Database initialization in lifespan notice: {exc}")

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
    VerifyClaimRequest,
    VerificationJobResponse,
    FeedbackCreateRequest,
    FeedbackItem,
    FeedbackListResponse,
)
from app.agents.decomposer import decompose_claim
from app.agents.judge import judge_evaluate_claim
from app.tools.web_search import search_web, WebSearchError
from app.tools.rag_retriever import retrieve_curated_evidence
from app.services.nli_verifier import get_nli_verifier
from app.services.feedback_store import get_feedback_store

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, IS_POSTGRES
from app.models.db_models import UserORM
from app.models.auth_schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse,
    HistorySyncRequest,
)
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_user_by_id,
)

def get_optional_user_id(authorization: Optional[str] = Header(None)) -> Optional[int]:
    """Extract user_id from optional Bearer token header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload and "sub" in payload:
        try:
            return int(payload["sub"])
        except ValueError:
            return None
    return None

def get_current_user_required(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> UserORM:
    """Require authenticated user from Bearer token header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    try:
        user_id = int(payload["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token user ID.",
        )
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )
    return user


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify service availability."""
    return {
        "status": "ok",
        "service": "veritas-api",
        "version": "0.1.0",
        "database": "postgresql" if IS_POSTGRES else "sqlite",
    }


# ---------------------------------------------------------------------------
# Authentication Endpoints
# ---------------------------------------------------------------------------
@app.post(
    "/api/auth/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register a new user account",
)
async def register_endpoint(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    try:
        user = register_user(db, payload)
        token = create_access_token(user.id, user.username)
        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                created_at=user.created_at.isoformat() if user.created_at else None,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post(
    "/api/auth/login",
    response_model=AuthTokenResponse,
    tags=["Authentication"],
    summary="Login with username or email and password",
)
async def login_endpoint(payload: UserLoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = authenticate_user(db, payload)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
        )
    token = create_access_token(user.id, user.username)
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ),
    )


@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Get profile of currently logged-in user",
)
async def get_me_endpoint(current_user: UserORM = Depends(get_current_user_required)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


# ---------------------------------------------------------------------------
# Cross-Device Audit History Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/api/history",
    tags=["History"],
    summary="Get audit history (persisted in database across devices for logged-in users)",
)
async def get_history_endpoint(
    limit: int = Query(30, ge=1, le=100),
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    from app.services.job_store import get_job_store
    job_store = get_job_store()
    if user_id is not None:
        return job_store.list_user_jobs(user_id=user_id, limit=limit)
    return job_store.list_recent_jobs(limit=limit)


@app.post(
    "/api/history/sync",
    tags=["History"],
    summary="Attach unauthenticated guest audits to logged-in user account in database",
)
async def sync_guest_history_endpoint(
    payload: HistorySyncRequest,
    current_user: UserORM = Depends(get_current_user_required),
):
    from app.services.job_store import get_job_store
    job_store = get_job_store()
    if payload.job_ids:
        job_store.assign_jobs_to_user(payload.job_ids, current_user.id)
    return job_store.list_user_jobs(user_id=current_user.id)


@app.get(
    "/api/history/{job_id}",
    response_model=VerificationJobResponse,
    tags=["History"],
    summary="Get single historical verification job by ID",
)
async def get_history_item_endpoint(job_id: str) -> VerificationJobResponse:
    from app.services.job_store import get_job_store
    job_store = get_job_store()
    job_data = job_store.get_job(job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification job '{job_id}' not found in database history.",
        )
    return VerificationJobResponse(**job_data)


@app.delete(
    "/api/history/{job_id}",
    tags=["History"],
    summary="Delete an audit from history",
)
async def delete_history_item(
    job_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    from app.services.job_store import get_job_store
    job_store = get_job_store()
    deleted = job_store.delete_job(job_id=job_id, user_id=user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit job not found or not owned by user.",
        )
    return {"status": "deleted", "job_id": job_id}


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
# End-to-End Verification Pipeline & Async Job System with Caching
# ---------------------------------------------------------------------------
import time
import uuid
from datetime import datetime, timezone
from app.models.schemas import VerifyClaimRequest, VerificationJobResponse
from app.agents.graph import run_verification_pipeline
from app.services.job_store import get_job_store, compute_claim_hash


async def _execute_verification_job(
    job_id: str,
    claim_text: str,
    generate_explanation: bool,
) -> None:
    """Background worker executing the complete Veritas multi-agent verification pipeline."""
    start_t = time.perf_counter()
    job_store = get_job_store()
    job_store.update_job_stage(job_id=job_id, status="processing", stage="decomposing")

    def _on_stage(stage_name: str) -> None:
        job_store.update_job_stage(job_id=job_id, status="processing", stage=stage_name)

    try:
        verdict_response = await run_verification_pipeline(
            raw_claim=claim_text,
            status_callback=_on_stage,
            generate_explanation=generate_explanation,
        )
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        token_count = verdict_response.tokens_used or 0
        result_dict = verdict_response.to_ui_dict()

        job_store.complete_job(
            job_id=job_id,
            result_dict=result_dict,
            latency_ms=latency_ms,
            token_count=token_count,
        )
        logger.info(
            f"Verification job {job_id} successfully completed in {latency_ms:.1f}ms | Verdict: {verdict_response.overall_verdict}"
        )

        # Store in semantic cache for instant future similarity matching
        try:
            from app.services.semantic_cache import get_semantic_cache
            from app.tools.rag_retriever import embed_text
            claim_emb = await embed_text(claim_text)
            sem_cache = get_semantic_cache()
            sem_cache.store(
                claim_text=claim_text,
                result_dict=result_dict,
                claim_embedding=claim_emb,
                verdict=verdict_response.overall_verdict,
                confidence=verdict_response.overall_confidence,
            )
        except Exception as sc_err:
            logger.debug(f"Semantic cache store notice: {sc_err}")
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        logger.exception(f"Verification job {job_id} failed after {latency_ms:.1f}ms: {exc}")
        job_store.fail_job(job_id=job_id, error_message=str(exc), latency_ms=latency_ms)


@app.post(
    "/api/verify",
    response_model=VerificationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Verification Pipeline"],
    summary="Enqueue asynchronous claim verification job (with instant cache check)",
    description="Submits a claim to the multi-agent verification pipeline. If an identical claim was recently verified, returns the result instantly from cache in milliseconds. Otherwise, creates a pending job and kicks off the run in the background.",
)
@app.post(
    "/verify",
    response_model=VerificationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def create_verification_job(
    payload: VerifyClaimRequest,
    background_tasks: BackgroundTasks,
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> VerificationJobResponse:
    try:
        claim_text = payload.resolved_claim()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    claim_hash = compute_claim_hash(claim_text)
    job_store = get_job_store()
    now_ts = datetime.now(timezone.utc).isoformat()

    # Step 1: Check instant exact cache hit
    cached_record = job_store.find_cached_job(claim_hash)
    if cached_record and cached_record.get("result"):
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        cache_latency = 1.2
        job_store.create_cached_job(
            job_id=job_id,
            raw_claim=claim_text,
            claim_hash=claim_hash,
            cached_result=cached_record["result"],
            latency_ms=cache_latency,
            user_id=user_id,
            cache_type="exact",
        )
        logger.info(f"⚡ EXACT CACHE HIT for claim '{claim_text[:50]}...'; returning stored verdict instantly.")
        return VerificationJobResponse(
            job_id=job_id,
            status="completed",
            stage="completed",
            claim=claim_text,
            created_at=now_ts,
            completed_at=now_ts,
            latency_ms=cache_latency,
            token_count=0,
            cached=True,
            cache_type="exact",
            result=cached_record["result"],
        )

    # Step 2: Check Semantic Cache (cosine similarity >= 0.88)
    try:
        from app.services.semantic_cache import get_semantic_cache
        from app.tools.rag_retriever import embed_text
        claim_emb = await embed_text(claim_text)
        sem_cache = get_semantic_cache()
        sem_hit = sem_cache.find_match(claim_text=claim_text, claim_embedding=claim_emb, threshold=0.88)
        if sem_hit:
            sem_result, sem_sim, matched_claim = sem_hit
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            cache_latency = 22.0
            job_store.create_cached_job(
                job_id=job_id,
                raw_claim=claim_text,
                claim_hash=claim_hash,
                cached_result=sem_result,
                latency_ms=cache_latency,
                user_id=user_id,
                cache_type="semantic",
                similarity=round(sem_sim, 4),
            )
            logger.info(
                f"⚡ SEMANTIC CACHE HIT (sim={sem_sim:.4f}) | '{claim_text[:40]}' matched '{matched_claim[:40]}'"
            )
            return VerificationJobResponse(
                job_id=job_id,
                status="completed",
                stage="completed",
                claim=claim_text,
                created_at=now_ts,
                completed_at=now_ts,
                latency_ms=cache_latency,
                token_count=0,
                cached=True,
                cache_type="semantic",
                similarity=round(sem_sim, 4),
                result=sem_result,
            )
    except Exception as sem_err:
        logger.debug(f"Semantic cache lookup notice: {sem_err}")

    # Step 3: Fresh verification run - enqueue as pending background job
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_store.create_job(
        job_id=job_id,
        raw_claim=claim_text,
        claim_hash=claim_hash,
        status="pending",
        stage="queued",
        user_id=user_id,
    )

    background_tasks.add_task(
        _execute_verification_job,
        job_id=job_id,
        claim_text=claim_text,
        generate_explanation=payload.generate_explanation,
    )

    logger.info(f"Enqueued pending verification job {job_id} for claim: {claim_text[:60]}... (user: {user_id})")
    return VerificationJobResponse(
        job_id=job_id,
        status="pending",
        stage="queued",
        claim=claim_text,
        created_at=now_ts,
        cached=False,
    )


@app.get(
    "/api/verify/{job_id}",
    response_model=VerificationJobResponse,
    tags=["Verification Pipeline"],
    summary="Poll verification job status and results",
    description="Polls current status ('pending', 'processing', 'completed', 'failed'). When completed, returns the full verdict, confidence, explanation, sub-claims with individual verdicts, and full evidence list with quotes, URLs, and NLI labels.",
)
@app.get(
    "/verify/{job_id}",
    response_model=VerificationJobResponse,
    include_in_schema=False,
)
async def get_verification_job(job_id: str) -> VerificationJobResponse:
    job_store = get_job_store()
    job_data = job_store.get_job(job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification job '{job_id}' not found.",
        )
    return VerificationJobResponse(**job_data)


@app.post(
    "/api/verify/sync",
    response_model=JudgeVerdictResponse,
    tags=["Verification Pipeline"],
    summary="Synchronous end-to-end claim verification",
    description="Directly executes full pipeline and blocks until final verdict is computed.",
)
@app.post(
    "/verify/sync",
    response_model=JudgeVerdictResponse,
    include_in_schema=False,
)
async def verify_claim_sync(payload: VerifyClaimRequest) -> JudgeVerdictResponse:
    try:
        claim_text = payload.resolved_claim()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        return await run_verification_pipeline(
            raw_claim=claim_text,
            generate_explanation=payload.generate_explanation,
        )
    except Exception as exc:
        logger.exception(f"Synchronous verification error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing verification pipeline: {str(exc)}",
        )


@app.post(
    "/api/feedback",
    response_model=FeedbackItem,
    status_code=status.HTTP_201_CREATED,
    tags=["Feedback"],
    summary="Submit user feedback on verification verdict",
    description="Submits thumbs-up or thumbs-down feedback and optional comment for a verification job, persisted to the feedback database.",
)
@app.post(
    "/feedback",
    response_model=FeedbackItem,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def submit_feedback(payload: FeedbackCreateRequest) -> FeedbackItem:
    feedback_store = get_feedback_store()
    try:
        record = feedback_store.add_feedback(
            job_id=payload.job_id,
            rating=payload.rating,
            verdict=payload.verdict or "",
            comment=payload.comment or "",
        )
        logger.info(f"Feedback recorded for job {payload.job_id}: {payload.rating} - {payload.comment[:40]}")
        return FeedbackItem(**record)
    except Exception as exc:
        logger.exception(f"Failed to record feedback: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing feedback: {str(exc)}",
        )


@app.get(
    "/api/feedback",
    response_model=FeedbackListResponse,
    tags=["Feedback"],
    summary="List feedback submissions (admin review)",
    description="Lists feedback records with optional filter by rating (e.g. 'thumbs_down' to review flagged errors).",
)
@app.get(
    "/feedback",
    response_model=FeedbackListResponse,
    include_in_schema=False,
)
async def list_feedback_endpoint(
    rating: Optional[str] = Query(None, description="Filter by rating: 'thumbs_up' or 'thumbs_down'"),
    limit: int = Query(100, ge=1, le=500, description="Max feedback rows to return"),
) -> FeedbackListResponse:
    feedback_store = get_feedback_store()
    try:
        items = feedback_store.list_feedback(rating=rating, limit=limit)
        return FeedbackListResponse(
            total=len(items),
            items=[FeedbackItem(**item) for item in items],
        )
    except Exception as exc:
        logger.exception(f"Failed to retrieve feedback list: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading feedback: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


