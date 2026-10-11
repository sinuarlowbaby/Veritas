import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.schemas import SearchResult
from app.tools.rag_retriever import (
    CANONICAL_SEED_FACTS,
    embed_text,
    ensure_curated_corpus_seeded,
    retrieve_curated_evidence,
)
from app.tools.web_search import search_web


# ---------------------------------------------------------------------------
# Step A Tests: Shape & Interchangeability
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_returns_search_result_shape():
    """Verify that retrieve_curated_evidence returns SearchResult instances with verdict metadata."""
    results = await retrieve_curated_evidence(
        query="Can papaya leaf extract or seeds cure dengue infection?",
        top_k=5,
    )
    assert len(results) > 0
    top = results[0]
    assert isinstance(top, SearchResult)
    assert hasattr(top, "title")
    assert hasattr(top, "url")
    assert hasattr(top, "snippet")
    assert hasattr(top, "content")
    assert hasattr(top, "source")
    assert hasattr(top, "verdict")
    assert hasattr(top, "publish_date")
    assert hasattr(top, "similarity")

    # Both tools share the exact same attributes
    assert top.source.startswith("curated_rag:")
    assert top.verdict is not None
    assert top.publish_date is not None
    assert top.similarity is not None


# ---------------------------------------------------------------------------
# Step B Tests: Relevance & Out-of-Corpus Discrimination
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_step_b_dengue_cure_relevance():
    """
    Test Step B relevance: A query about dengue cures must return the papaya seeds
    chunk at rank 1, NOT the moon landing or anthem chunks.
    """
    query = "Papaya leaves and seeds cure dengue fever in 48 hours"
    results = await retrieve_curated_evidence(query=query, top_k=5)

    assert len(results) >= 3
    top_result = results[0]

    # Verify rank 1 is specifically the papaya dengue fact check
    assert "papaya" in top_result.title.lower() or "dengue" in top_result.title.lower()
    assert top_result.verdict == "FALSE"
    assert top_result.similarity > 0.65

    # Verify moon landing and national anthem chunks are not the top match
    assert "moon" not in top_result.title.lower()
    assert "anthem" not in top_result.title.lower()

    # Verify significant similarity gap between relevant match and unrelated items
    top_score = top_result.similarity
    anthem_score = next((r.similarity for r in results if "anthem" in r.title.lower()), 0.0)
    assert top_score - anthem_score > 0.35, "Expected strong semantic separation"


@pytest.mark.asyncio
async def test_step_b_decomposer_subclaims_relevance():
    """
    Test Step B with real sub-claims from earlier decomposer tests:
    1. Green tea COVID-19 cure claim
    2. 5G tower radiation bird deaths claim
    3. Senior citizen income tax elimination claim
    """
    test_cases = [
        {
            "sub_claim": "WHO officially confirmed green tea cures COVID-19 in 48 hours",
            "expected_keyword": "green tea",
            "expected_verdict": "FALSE",
        },
        {
            "sub_claim": "5G mobile tower radiation caused mysterious bird deaths in Delhi",
            "expected_keyword": "5g",
            "expected_verdict": "FALSE",
        },
        {
            "sub_claim": "Finance Ministry eliminated all income tax for senior citizens over 60",
            "expected_keyword": "income tax",
            "expected_verdict": "FALSE",
        },
    ]

    for tc in test_cases:
        results = await retrieve_curated_evidence(query=tc["sub_claim"], top_k=3)
        assert len(results) > 0
        top = results[0]
        assert tc["expected_keyword"] in top.title.lower() or tc["expected_keyword"] in top.content.lower()
        assert top.verdict == tc["expected_verdict"]
        assert top.similarity >= 0.65


@pytest.mark.asyncio
async def test_step_b_out_of_corpus_low_similarity():
    """
    Test Step B out-of-corpus discrimination:
    Run sub-claims about cricket and cinema that are not in the corpus.
    Similarity score must be distinctly low (< 0.45), providing the critical
    signal for the Judge to fall back to web search and abstention.
    """
    out_of_corpus_queries = [
        "Virat Kohli scored his 50th century in the ODI World Cup semi-final at Wankhede Stadium",
        "Shah Rukh Khan's movie Jawan broke box office records across Mumbai theaters",
    ]

    for query in out_of_corpus_queries:
        results = await retrieve_curated_evidence(query=query, top_k=3)
        assert len(results) > 0
        top_score = results[0].similarity
        # Verify the top similarity score is low
        assert top_score < 0.45, (
            f"Expected low similarity (< 0.45) for out-of-corpus query '{query}', "
            f"but got {top_score:.4f}"
        )


# ---------------------------------------------------------------------------
# Step C Tests: Side-by-Side Comparison on Identical Sub-Claim
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_step_c_side_by_side_comparison():
    """
    Test Step C comparison: Run one sub-claim through both search_web and
    retrieve_curated_evidence side by side.
    Verify:
    1. Both return the SearchResult shape (interchangeable).
    2. RAG result carries an authoritative verdict ('FALSE'), whereas web result has verdict=None.
    """
    sub_claim = "WHO officially confirms green tea cures COVID-19 in 48 hours"

    # 1. RAG retrieval
    rag_results = await retrieve_curated_evidence(query=sub_claim, top_k=3)
    assert len(rag_results) > 0
    rag_top = rag_results[0]

    # 2. Web search (mocked or live fallback)
    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        mock_web_results = [
            SearchResult(
                title="Did WHO say green tea cures COVID-19? Live Web Report",
                url="https://example.com/news/who-green-tea-report",
                snippet="Social media posts circulate claiming WHO issued guidance...",
                content="Full news report text from web scraper without formal verdict...",
                source="duckduckgo",
                verdict=None,
                publish_date=None,
                similarity=None,
            )
        ]
        mock_tf.return_value = mock_web_results

        web_results = await search_web(query=sub_claim, max_results=3)

    assert len(web_results) > 0
    web_top = web_results[0]

    # Both conform to SearchResult
    assert isinstance(rag_top, SearchResult)
    assert isinstance(web_top, SearchResult)

    # Note the fundamental difference: Curated RAG carries professional verdict & similarity
    assert rag_top.verdict in ("FALSE", "TRUE", "MISLEADING")
    assert rag_top.similarity is not None
    assert rag_top.source.startswith("curated_rag:")

    # Web search does not carry a pre-established verdict
    assert web_top.verdict is None
    assert web_top.similarity is None
    assert web_top.source in ("tinyfish", "tavily", "duckduckgo")


@pytest.mark.asyncio
async def test_fastapi_rag_endpoint():
    """Test FastAPI /api/rag endpoint (POST & GET)."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Test POST /api/rag
        post_resp = await client.post(
            "/api/rag",
            json={"question": "Can papaya seeds cure dengue?", "max_results": 2},
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert post_data["question"] == "Can papaya seeds cure dengue?"
        assert post_data["provider_used"].startswith("curated_rag:")
        assert post_data["total_results"] == 2
        assert post_data["results"][0]["verdict"] == "FALSE"

        # Test GET /api/rag
        get_resp = await client.get(
            "/api/rag",
            params={"question": "WHO green tea COVID cure", "max_results": 1},
        )
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["total_results"] == 1
        assert get_data["results"][0]["verdict"] == "FALSE"
