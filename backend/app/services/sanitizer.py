import html
import logging
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from app.models.schemas import EvidenceItem, SearchResult

logger = logging.getLogger("veritas.sanitizer")

# ---------------------------------------------------------------------------
# Known Domain Classifications
# ---------------------------------------------------------------------------
IFCN_FACT_CHECK_DOMAINS = {
    "altnews.in",
    "boomlive.in",
    "snopes.com",
    "politifact.com",
    "factcheck.org",
    "fullfact.org",
    "thequint.com",
    "vishvasnews.com",
    "newsmobile.in",
    "thip.media",
    "leadstories.com",
    "checkyourfact.com",
    "climatefeedback.org",
    "healthfeedback.org",
    "afp.com",
    "factcheck.afp.com",
}

OFFICIAL_GOV_DOMAINS = {
    "who.int",
    "un.org",
    "cdc.gov",
    "nih.gov",
    "fda.gov",
    "pib.gov.in",
    "isro.gov.in",
    "incometax.gov.in",
    "incometaxindia.gov.in",
    "rbi.org.in",
    "mohfw.gov.in",
    "mygov.in",
    "unicef.org",
    "unesco.org",
    "nasa.gov",
    "dot.gov.in",
}

MAINSTREAM_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "thehindu.com",
    "indianexpress.com",
    "ndtv.com",
    "hindustantimes.com",
    "timesofindia.indiatimes.com",
    "theguardian.com",
    "nytimes.com",
    "washingtonpost.com",
    "bloomberg.com",
    "nature.com",
    "science.org",
    "thelancet.com",
    "bmj.com",
    "nejm.org",
    "wikipedia.org",
    "britannica.com",
    "dw.com",
    "aljazeera.com",
    "cnn.com",
    "nbcnews.com",
    "wsj.com",
    "forbes.com",
    "economist.com",
    "scientificamerican.com",
}


def extract_clean_domain(url: str) -> str:
    """
    Extracts the root/hostname from a URL, stripping 'www.' and lowercasing.
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def determine_domain_tier(domain: str, is_curated: bool = False, source: str = "") -> int:
    """
    Determines credibility tier according to Veritas rules:
      - Tier 1: Curated IFCN fact-checkers (Alt News, BoomLive, Snopes, etc.)
      - Tier 2: Government agencies, official registries, multilateral bodies (WHO, PIB, etc.)
      - Tier 3: Reputable mainstream journalism, peer-reviewed journals, reference
      - Tier 4: General web search results, unverified publications, blog posts
    """
    if is_curated or source.startswith("curated_rag"):
        return 1

    clean_dom = domain.lower().strip()
    if not clean_dom:
        return 4

    # Tier 1 check
    if clean_dom in IFCN_FACT_CHECK_DOMAINS or any(clean_dom.endswith("." + d) for d in IFCN_FACT_CHECK_DOMAINS):
        return 1

    # Tier 2 check (gov, int, mil, official agencies)
    if (
        clean_dom.endswith(".gov")
        or clean_dom.endswith(".gov.in")
        or clean_dom.endswith(".nic.in")
        or clean_dom.endswith(".mil")
        or clean_dom.endswith(".int")
        or clean_dom in OFFICIAL_GOV_DOMAINS
        or any(clean_dom.endswith("." + d) for d in OFFICIAL_GOV_DOMAINS)
    ):
        return 2

    # Tier 3 check
    if clean_dom in MAINSTREAM_NEWS_DOMAINS or any(clean_dom.endswith("." + d) for d in MAINSTREAM_NEWS_DOMAINS):
        return 3

    # Default Tier 4
    return 4


def clean_text_quote(raw_text: str, max_chars: int = 400) -> str:
    """
    Cleans, strips HTML tags, and truncates text to form a clean quote.
    """
    if not raw_text:
        return ""

    # Unescape HTML entities
    text = html.unescape(raw_text)

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        # Truncate at sentence boundary or word boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind(".")
        if last_period > max_chars * 0.6:
            text = truncated[: last_period + 1]
        else:
            last_space = truncated.rfind(" ")
            if last_space > 0:
                text = truncated[:last_space] + "..."
            else:
                text = truncated + "..."

    return text


def sanitize_evidence_item(item: EvidenceItem) -> Optional[EvidenceItem]:
    """
    Sanitizes a single EvidenceItem:
      - Validates non-empty quote (>= 15 characters)
      - Validates HTTP/HTTPS URL
      - Normalizes domain and assigns tier
    Returns None if item fails validation.
    """
    clean_quote = clean_text_quote(item.quote)
    if len(clean_quote) < 15:
        return None

    url = (item.source_url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None

    domain = extract_clean_domain(url)
    if not domain:
        domain = item.domain or "unknown"

    tier = determine_domain_tier(domain, is_curated=item.curated, source=item.source_url)

    item.quote = clean_quote
    item.domain = domain
    item.domain_tier = tier
    return item


def sanitize_evidence(
    evidence_items: List[EvidenceItem],
    max_per_domain_per_subclaim: int = 2,
) -> List[EvidenceItem]:
    """
    Sanitizes, validates, and deduplicates evidence items:
      - Validates non-empty verbatim quotes and valid HTTP URLs
      - Extracts clean domains and assigns credibility tiers (1, 2, 3, 4)
      - Caps evidence to `max_per_domain_per_subclaim` to avoid single-domain bias
      - Removes exact duplicate quotes
    """
    cleaned: List[EvidenceItem] = []
    seen_quotes: Set[str] = set()
    domain_counts: Dict[str, int] = {}

    for item in evidence_items:
        sanitized = sanitize_evidence_item(item)
        if not sanitized:
            continue

        quote_key = sanitized.quote.lower()[:80]
        if quote_key in seen_quotes:
            continue

        sc_domain_key = f"{sanitized.sub_claim_id}:{sanitized.domain}"
        count = domain_counts.get(sc_domain_key, 0)
        if count >= max_per_domain_per_subclaim:
            continue

        seen_quotes.add(quote_key)
        domain_counts[sc_domain_key] = count + 1
        cleaned.append(sanitized)

    return cleaned


def search_result_to_evidence(
    result: SearchResult,
    sub_claim_id: str,
    sub_claim: str,
    retrieved_by: str = "proponent",
) -> Optional[EvidenceItem]:
    """
    Converts a SearchResult (from web_search or rag_retriever) into an EvidenceItem.
    Extracts the most salient quote from content or snippet.
    """
    # Pick the best candidate quote text
    content_text = (result.content or "").strip()
    snippet_text = (result.snippet or "").strip()

    raw_quote = ""
    if content_text and len(content_text) >= 30:
        raw_quote = content_text
    elif snippet_text and len(snippet_text) >= 15:
        raw_quote = snippet_text
    elif result.title:
        raw_quote = result.title

    clean_quote = clean_text_quote(raw_quote, max_chars=350)
    if len(clean_quote) < 15:
        return None

    domain = extract_clean_domain(result.url)
    is_curated = result.source.startswith("curated_rag")
    domain_tier = determine_domain_tier(domain, is_curated=is_curated, source=result.source)

    return EvidenceItem(
        sub_claim_id=sub_claim_id,
        sub_claim=sub_claim,
        quote=clean_quote,
        source_url=result.url,
        domain=domain,
        domain_tier=domain_tier,
        publish_date=result.publish_date,
        retrieved_by=retrieved_by,
        curated=is_curated,
    )
