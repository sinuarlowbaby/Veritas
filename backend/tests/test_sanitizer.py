import pytest

from app.models.schemas import EvidenceItem, SearchResult
from app.services.sanitizer import (
    clean_text_quote,
    determine_domain_tier,
    extract_clean_domain,
    sanitize_evidence,
    search_result_to_evidence,
)


def test_extract_clean_domain():
    assert extract_clean_domain("https://www.boomlive.in/fact-check/article-1") == "boomlive.in"
    assert extract_clean_domain("http://who.int/emergencies/disease") == "who.int"
    assert extract_clean_domain("https://subdomain.pib.gov.in:8080/press-release") == "subdomain.pib.gov.in"
    assert extract_clean_domain("invalid-url") == ""
    assert extract_clean_domain("") == ""


def test_determine_domain_tier():
    # Tier 1: Fact Checkers
    assert determine_domain_tier("boomlive.in") == 1
    assert determine_domain_tier("altnews.in") == 1
    assert determine_domain_tier("snopes.com") == 1

    # Tier 2: Government & Multilateral
    assert determine_domain_tier("who.int") == 2
    assert determine_domain_tier("pib.gov.in") == 2
    assert determine_domain_tier("cdc.gov") == 2
    assert determine_domain_tier("dot.gov.in") == 2

    # Tier 3: Mainstream journalism / journals
    assert determine_domain_tier("reuters.com") == 3
    assert determine_domain_tier("bbc.com") == 3
    assert determine_domain_tier("thehindu.com") == 3
    assert determine_domain_tier("nature.com") == 3

    # Tier 4: General web / blog
    assert determine_domain_tier("random-conspiracy-blog.com") == 4
    assert determine_domain_tier("someforum.net") == 4

    # Curated flag override
    assert determine_domain_tier("unknown-source.org", is_curated=True) == 1


def test_clean_text_quote():
    raw_html = "<p>Doctors confirm that <b>green tea</b> does <i>not</i> cure COVID-19.</p>"
    cleaned = clean_text_quote(raw_html)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "Doctors confirm that green tea does not cure COVID-19." in cleaned

    # Length capping
    long_text = "Word " * 200
    cleaned_long = clean_text_quote(long_text, max_chars=100)
    assert len(cleaned_long) <= 105


def test_sanitize_evidence_deduplication():
    items = [
        # Valid item 1
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="The World Health Organization confirmed there is no cure using herbal tea.",
            source_url="https://who.int/news/item",
        ),
        # Duplicate domain item 2 (allowed up to 2)
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Second valid quote from the World Health Organization official bulletin.",
            source_url="https://who.int/news/another-bulletin",
        ),
        # 3rd item from same domain -> should be dropped (max 2 per domain per sub-claim)
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Third quote from WHO which should exceed the single domain cap for sc_1.",
            source_url="https://who.int/news/third-bulletin",
        ),
        # Duplicate quote text -> should be dropped
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="The World Health Organization confirmed there is no cure using herbal tea.",
            source_url="https://reuters.com/news/reuters-copy",
        ),
        # Invalid URL -> should be dropped
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="This quote has an invalid URL schema and should be dropped.",
            source_url="ftp://ftp.example.com/file",
        ),
        # Quote too short -> should be dropped
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Too short",
            source_url="https://thehindu.com/news",
        ),
    ]

    sanitized = sanitize_evidence(items, max_per_domain_per_subclaim=2)
    assert len(sanitized) == 2
    assert sanitized[0].domain == "who.int"
    assert sanitized[0].domain_tier == 2
    assert sanitized[1].domain == "who.int"


def test_search_result_to_evidence():
    result = SearchResult(
        title="Fact Check: Green Tea does not cure COVID",
        url="https://www.boomlive.in/fact-check/green-tea-covid",
        snippet="BoomLive investigation shows viral message about green tea curing COVID in 48 hours is false.",
        content="Viral claims asserting that drinking hot green tea cures COVID-19 are false. WHO and ICMR confirmed this.",
        source="curated_rag:BoomLive",
        verdict="FALSE",
        publish_date="2021-05-10",
    )

    ev = search_result_to_evidence(
        result=result,
        sub_claim_id="sc_1",
        sub_claim="Green tea cures COVID-19",
        retrieved_by="skeptic",
    )

    assert ev is not None
    assert ev.sub_claim_id == "sc_1"
    assert ev.domain == "boomlive.in"
    assert ev.domain_tier == 1  # BoomLive + curated_rag = Tier 1
    assert ev.retrieved_by == "skeptic"
    assert ev.curated is True
    assert "cures COVID-19 are false" in ev.quote
