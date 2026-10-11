import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.schemas import SearchResult
from app.tools.web_search import (
    WebSearchError,
    _search_duckduckgo,
    _search_tavily,
    _search_tinyfish,
    search_web,
)


@pytest.mark.asyncio
async def test_search_result_model():
    """Verify SearchResult model structure and required fields."""
    res = SearchResult(
        title="Test Title",
        url="https://example.com/test",
        snippet="A snippet description",
        content="# Full Page Content",
        source="tinyfish",
    )
    assert res.title == "Test Title"
    assert res.url == "https://example.com/test"
    assert res.snippet == "A snippet description"
    assert res.content == "# Full Page Content"
    assert res.source == "tinyfish"


@pytest.mark.asyncio
async def test_tinyfish_primary_success():
    """Test that TinyFish succeeds and Tavily / DDG are not called."""
    mock_tinyfish_results = [
        SearchResult(
            title="TinyFish Result 1",
            url="https://example.com/1",
            snippet="Snippet 1",
            content="# Page 1 Markdown text",
            source="tinyfish",
        )
    ]

    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        mock_tf.return_value = mock_tinyfish_results

        results = await search_web("quantum computing", max_results=5, backoff_delay=0.01)

        assert len(results) == 1
        assert results[0].source == "tinyfish"
        assert results[0].title == "TinyFish Result 1"
        assert results[0].content == "# Page 1 Markdown text"
        assert mock_tf.call_count == 1
        assert mock_tav.call_count == 0
        assert mock_ddg.call_count == 0


@pytest.mark.asyncio
async def test_tinyfish_retry_success():
    """Test that if TinyFish fails on attempt 1, it retries once with backoff and succeeds."""
    mock_tinyfish_results = [
        SearchResult(
            title="TinyFish Result on Retry",
            url="https://example.com/retry",
            snippet="Snippet",
            content="Content",
            source="tinyfish",
        )
    ]

    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        # Attempt 1 fails, Attempt 2 succeeds
        mock_tf.side_effect = [RuntimeError("TinyFish 429 Rate Limit"), mock_tinyfish_results]

        results = await search_web("climate policy", max_results=5, backoff_delay=0.01)

        assert len(results) == 1
        assert results[0].source == "tinyfish"
        assert results[0].title == "TinyFish Result on Retry"
        assert mock_tf.call_count == 2  # 1 initial + 1 retry
        assert mock_tav.call_count == 0
        assert mock_ddg.call_count == 0


@pytest.mark.asyncio
async def test_fallback_to_tavily_on_tinyfish_failure():
    """Test fallback to Tavily when TinyFish fails both attempts."""
    mock_tavily_results = [
        SearchResult(
            title="Tavily Result",
            url="https://example.com/tavily",
            snippet="Tavily snippet",
            content="Tavily raw article content",
            source="tavily",
        )
    ]

    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        # TinyFish fails on both attempts
        mock_tf.side_effect = RuntimeError("TinyFish outage")
        mock_tav.return_value = mock_tavily_results

        results = await search_web("renewable energy", max_results=3, backoff_delay=0.01)

        assert len(results) == 1
        assert results[0].source == "tavily"
        assert results[0].content == "Tavily raw article content"
        assert mock_tf.call_count == 2  # Attempt 1 + 1 retry
        assert mock_tav.call_count == 1
        assert mock_ddg.call_count == 0


@pytest.mark.asyncio
async def test_fallback_to_duckduckgo_when_tinyfish_and_tavily_fail():
    """Test fallback to DuckDuckGo when TinyFish and Tavily both fail."""
    mock_ddg_results = [
        SearchResult(
            title="DuckDuckGo Result",
            url="https://example.com/ddg",
            snippet="DDG snippet",
            content="DDG extracted page text",
            source="duckduckgo",
        )
    ]

    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        mock_tf.side_effect = ValueError("TINYFISH_API_KEY environment variable is not set")
        mock_tav.side_effect = RuntimeError("Tavily rate limit exceeded (HTTP 429)")
        mock_ddg.return_value = mock_ddg_results

        results = await search_web("machine learning models", max_results=5, backoff_delay=0.01)

        assert len(results) == 1
        assert results[0].source == "duckduckgo"
        assert results[0].title == "DuckDuckGo Result"
        assert mock_tf.call_count == 2
        assert mock_tav.call_count == 2
        assert mock_ddg.call_count == 1


@pytest.mark.asyncio
async def test_all_three_providers_fail_raises_clear_error():
    """Verify that WebSearchError is raised with clear provider error details if all 3 fail."""
    with patch("app.tools.web_search._search_tinyfish", new_callable=AsyncMock) as mock_tf, \
         patch("app.tools.web_search._search_tavily", new_callable=AsyncMock) as mock_tav, \
         patch("app.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_ddg:

        mock_tf.side_effect = ValueError("TINYFISH_API_KEY environment variable is not set")
        mock_tav.side_effect = RuntimeError("Tavily 429 Rate Limit")
        mock_ddg.side_effect = RuntimeError("DuckDuckGo 403 Ratelimit")

        with pytest.raises(WebSearchError) as exc_info:
            await search_web("unreachable query", max_results=5, backoff_delay=0.01)

        err_msg = str(exc_info.value)
        assert "All web search providers failed for query" in err_msg
        assert "tinyfish" in err_msg
        assert "tavily" in err_msg
        assert "duckduckgo" in err_msg


@pytest.mark.asyncio
async def test_live_duckduckgo_fallback():
    """
    Test live DuckDuckGo provider (or resilient handling if offline).
    Ensures _sync_ddgs_search and SearchResult conversion works end-to-end.
    """
    try:
        results = await _search_duckduckgo("python programming language", max_results=2)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.source == "duckduckgo"
            assert len(r.title) > 0
            assert len(r.url) > 0
            assert len(r.snippet) > 0
    except Exception as exc:
        # If external network blocks DuckDuckGo in test environment, verify exception is caught cleanly
        assert isinstance(exc, (RuntimeError, ValueError))


@pytest.mark.asyncio
async def test_fastapi_search_endpoints():
    """Test FastAPI /api/search (POST & GET) and /api/search/batch endpoints."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    mock_results = [
        SearchResult(
            title="FastAPI Search Result",
            url="https://fastapi.tiangolo.com",
            snippet="High performance API framework",
            content="FastAPI documentation and tutorial page content.",
            source="tinyfish",
        )
    ]

    with patch("app.main.search_web", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            # 1. Test POST /api/search
            post_resp = await client.post(
                "/api/search",
                json={"question": "How does FastAPI work?", "max_results": 2},
            )
            assert post_resp.status_code == 200
            post_data = post_resp.json()
            assert post_data["question"] == "How does FastAPI work?"
            assert post_data["provider_used"] == "tinyfish"
            assert post_data["total_results"] == 1
            assert post_data["results"][0]["title"] == "FastAPI Search Result"

            # 2. Test GET /api/search
            get_resp = await client.get(
                "/api/search",
                params={"question": "FastAPI tutorial", "max_results": 1},
            )
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["question"] == "FastAPI tutorial"
            assert get_data["total_results"] == 1

            # 3. Test POST /api/search/batch
            batch_resp = await client.post(
                "/api/search/batch",
                json={
                    "questions": ["Question 1", "Question 2"],
                    "max_results": 1,
                },
            )
            assert batch_resp.status_code == 200
            batch_data = batch_resp.json()
            assert batch_data["total_questions"] == 2
            assert len(batch_data["responses"]) == 2

