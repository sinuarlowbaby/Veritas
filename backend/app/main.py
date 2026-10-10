import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from fastapi import FastAPI
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
    description="A Multi-Agent Debate System for Fake News Verification",
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

from app.models.schemas import DecomposeRequest, DecomposeResponse
from app.agents.decomposer import decompose_claim

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
