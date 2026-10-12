import asyncio
import logging
import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional

warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import httpx

# Load environment variables (.env from backend or root)
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

from app.models.schemas import SearchResult

logger = logging.getLogger("veritas.tools.web_search")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for Web Search.")
else:
    def observe(*args, **kwargs):
        """Pass-through decorator when Langfuse is not enabled."""
        def decorator(fn):
            return fn
        return decorator

    logger.info("Langfuse credentials not set; running Web Search with standard logging.")


class WebSearchError(RuntimeError):
    """Raised when all web search providers in the fallback chain fail."""
    pass


# ---------------------------------------------------------------------------
# Provider 1: TinyFish (Primary) - Search API + Fetch API
# ---------------------------------------------------------------------------
async def _search_tinyfish(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    Search using TinyFish Search API and fetch clean browser-rendered content
    via TinyFish Fetch API.
    """
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("TINYFISH_API_KEY environment variable is not set")

    headers = {
        "X-API-Key": api_key.strip(),
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Step 1: Search API
        search_resp = await client.get(
            "https://api.search.tinyfish.ai",
            params={"query": query},
            headers=headers,
        )

        if search_resp.status_code == 429:
            raise RuntimeError("TinyFish Search API rate limit exceeded (HTTP 429)")
        search_resp.raise_for_status()

        search_data = search_resp.json()
        raw_items = search_data.get("results", [])
        if not raw_items:
            raise ValueError(f"TinyFish search returned 0 results for query: '{query}'")

        top_items = raw_items[:max_results]
        urls_to_fetch = [
            item.get("url")
            for item in top_items
            if item.get("url") and str(item.get("url")).startswith("http")
        ]

        # Step 2: Fetch API for clean browser-rendered text
        content_map: Dict[str, str] = {}
        if urls_to_fetch:
            try:
                fetch_resp = await client.post(
                    "https://api.fetch.tinyfish.ai",
                    json={"urls": urls_to_fetch, "format": "markdown"},
                    headers={**headers, "Content-Type": "application/json"},
                )
                if fetch_resp.status_code == 429:
                    raise RuntimeError("TinyFish Fetch API rate limit exceeded (HTTP 429)")
                fetch_resp.raise_for_status()

                fetch_data = fetch_resp.json()
                for item in fetch_data.get("results", []):
                    u = item.get("url", "")
                    # Support text, markdown, or content returned by Fetch API
                    text = item.get("text") or item.get("markdown") or item.get("content") or ""
                    if u and text:
                        content_map[u] = text.strip()
            except Exception as fetch_err:
                logger.warning(
                    f"TinyFish Fetch API call failed ({fetch_err}); falling back to snippet text."
                )

        results: List[SearchResult] = []
        for item in top_items:
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            content = content_map.get(url) or snippet
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=snippet,
                    content=content,
                    source="tinyfish",
                )
            )

        return results


# ---------------------------------------------------------------------------
# Provider 2: Tavily (Backup) - Raw API / AsyncTavilyClient
# ---------------------------------------------------------------------------
async def _search_tavily(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    Search using Tavily API (with raw content extraction).
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("TAVILY_API_KEY environment variable is not set")

    # Try official AsyncTavilyClient first, fallback to raw HTTP if needed
    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=api_key.strip())
        response_dict = await client.search(
            query=query,
            max_results=max_results,
            include_raw_content=True,
            timeout=20.0,
        )
        raw_items = response_dict.get("results", [])
    except ImportError:
        # Fallback to direct HTTP request
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key.strip(),
                    "query": query,
                    "max_results": max_results,
                    "include_raw_content": True,
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            if resp.status_code == 429:
                raise RuntimeError("Tavily rate limit exceeded (HTTP 429)")
            resp.raise_for_status()
            data = resp.json()
            raw_items = data.get("results", [])

    if not raw_items:
        raise ValueError(f"Tavily returned 0 results for query: '{query}'")

    results: List[SearchResult] = []
    for item in raw_items[:max_results]:
        url = item.get("url", "")
        snippet = item.get("content", "")
        content = item.get("raw_content") or snippet
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=snippet,
                content=content,
                source="tavily",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Provider 3: DuckDuckGo (Last Resort) - Unofficial duckduckgo-search
# ---------------------------------------------------------------------------
def _sync_ddgs_search(keywords: str, max_res: int) -> List[dict]:
    """
    Synchronous helper for duckduckgo-search with resilient fallbacks
    across text, html, and news methods.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

    # 1. Primary DDGS text search
    try:
        with DDGS() as ddgs:
            res = ddgs.text(keywords=keywords, max_results=max_res)
            if res:
                results = list(res)
    except Exception as e:
        logger.debug(f"DDGS text() attempt encountered error: {e}")

    # 2. Resilient fallback to HTML scraper if text returned empty
    if not results:
        try:
            with DDGS() as ddgs:
                if hasattr(ddgs, "_text_html"):
                    res = ddgs._text_html(keywords, None, None, max_res)
                    if res:
                        results = list(res)
        except Exception as e:
            logger.debug(f"DDGS _text_html() attempt encountered error: {e}")

    # 3. Resilient fallback to news scraper if still empty
    if not results:
        try:
            with DDGS() as ddgs:
                res = ddgs.news(keywords=keywords, max_results=max_res)
                if res:
                    results = list(res)
        except Exception as e:
            logger.debug(f"DDGS news() attempt encountered error: {e}")

    return results


async def _fetch_webpage_content(url: str, fallback_snippet: str) -> str:
    """
    Best-effort async extraction of readable text from a URL for DDG results.
    """
    if not url or not url.startswith("http"):
        return fallback_snippet

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "form"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                if text and len(text.strip()) > 50:
                    return text.strip()[:10000]
    except Exception:
        pass

    return fallback_snippet


async def _search_duckduckgo(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    Search using unofficial duckduckgo-search wrapped in try/except and executed
    in an async thread executor to avoid event loop blocking.
    """
    try:
        raw_items = await asyncio.to_thread(_sync_ddgs_search, query, max_results)
    except Exception as exc:
        raise RuntimeError(f"DuckDuckGo search error: {exc}") from exc

    if not raw_items:
        raise ValueError(f"DuckDuckGo search returned 0 results for query: '{query}'")

    selected_items = raw_items[:max_results]

    # Best-effort concurrent page content extraction
    tasks = [
        _fetch_webpage_content(
            item.get("href") or item.get("url", ""),
            item.get("body") or item.get("snippet", ""),
        )
        for item in selected_items
    ]
    extracted_contents = await asyncio.gather(*tasks)

    results: List[SearchResult] = []
    for item, content in zip(selected_items, extracted_contents):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("href") or item.get("url", ""),
                snippet=item.get("body") or item.get("snippet", ""),
                content=content,
                source="duckduckgo",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Main Search Web Orchestrator Function
# ---------------------------------------------------------------------------
@observe(name="search_web")
async def search_web(
    query: str,
    max_results: int = 5,
    backoff_delay: float = 1.0,
) -> List[SearchResult]:
    """
    Search the live web with a resilient provider fallback chain:
      1. TinyFish (primary)   - Search API + Fetch API for clean browser-rendered text
      2. Tavily (backup)      - Tavily API with full raw content extraction
      3. DuckDuckGo (last resort) - duckduckgo-search with HTML/text fallback

    - Retries each provider once with exponential backoff before falling back.
    - Logs which provider succeeded and result count (integrated with Langfuse tracing).
    - Raises WebSearchError only if all three providers fail.

    Args:
        query: Search query string.
        max_results: Maximum number of search results to return (default: 5).
        backoff_delay: Base exponential backoff delay in seconds for retries (default: 1.0s).

    Returns:
        List[SearchResult] with title, url, snippet, content, and source.
    """
    providers = [
        ("tinyfish", _search_tinyfish),
        ("tavily", _search_tavily),
        ("duckduckgo", _search_duckduckgo),
    ]

    errors: Dict[str, str] = {}

    for provider_name, provider_fn in providers:
        last_error: Optional[Exception] = None

        # Try provider: attempt 0 (initial), attempt 1 (retry with backoff)
        for attempt in range(2):
            try:
                results = await provider_fn(query=query, max_results=max_results)
                if results and len(results) > 0:
                    logger.info(
                        "Web search successful via provider: '%s' | returned %d results for query: '%s'",
                        provider_name,
                        len(results),
                        query,
                    )
                    return results
                else:
                    raise ValueError(f"Provider '{provider_name}' returned 0 results")
            except Exception as exc:
                last_error = exc
                is_missing_key = (
                    isinstance(exc, (ValueError, KeyError))
                    and "api key" in str(exc).lower()
                )

                if attempt == 0:
                    # For missing keys, skip sleep delay to avoid unnecessary waiting
                    delay = 0.0 if is_missing_key else backoff_delay
                    if delay > 0:
                        logger.warning(
                            "Provider '%s' attempt 1 failed: %s. Retrying once in %.1fs with exponential backoff...",
                            provider_name,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            "Provider '%s' attempt 1 failed: %s. Retrying once immediately...",
                            provider_name,
                            exc,
                        )
                else:
                    logger.warning(
                        "Provider '%s' retry attempt 2 failed: %s. Moving to next provider in fallback chain.",
                        provider_name,
                        exc,
                    )

        if last_error is not None:
            errors[provider_name] = str(last_error)

    # If all three providers fail, raise a clear error
    error_summary = "\n".join(f"  - {p}: {err}" for p, err in errors.items())
    logger.error(
        "All 3 web search providers failed for query '%s':\n%s",
        query,
        error_summary,
    )
    raise WebSearchError(
        f"All web search providers failed for query '{query}'.\n"
        f"Provider errors:\n{error_summary}"
    )


__all__ = ["search_web", "SearchResult", "WebSearchError"]
