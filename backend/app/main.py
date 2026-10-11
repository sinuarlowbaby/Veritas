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
    logger.info("Starting up Veritas API...")
    logger.info("Running on http://localhost:8000")
    logger.info("docs at http://localhost:8000/docs")
    # Initialize resources (e.g. DB pools, RAG retriever, model caches) here if needed
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
)
from app.agents.decomposer import decompose_claim
from app.tools.web_search import search_web, WebSearchError

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



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
