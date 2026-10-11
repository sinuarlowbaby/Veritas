from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.schemas import (
    EvidenceItem,
    JudgeVerdictRequest,
    JudgeVerdictResponse,
    SubClaim,
    SubClaimVerdict,
)
from app.agents.judge import (
    ABSTENTION_SCORE_THRESHOLD,
    FALSE_THRESHOLD,
    MIN_EVIDENCE_COUNT,
    TIER_WEIGHTS,
    TRUE_THRESHOLD,
    aggregate_verdicts,
    calculate_recency_decay,
    calculate_sub_claim_score,
    determine_sub_claim_verdict,
    explain_verdict_with_llm,
    judge_evaluate_claim,
)


# ---------------------------------------------------------------------------
# Part 1 Tests: Pure Math Scoring & Recency Decay
# ---------------------------------------------------------------------------
def test_pure_math_scoring_supports_and_refutes():
    """
    Test deterministic math scoring formula:
      Score = sum(tier * conf * decay for SUPPORTS) - sum(tier * conf * decay for REFUTES)
    """
    fixed_ref_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # 1 Tier 1 SUPPORTS (weight 1.0, conf 0.9, recent -> 0.9)
    # 1 Tier 3 SUPPORTS (weight 0.5, conf 0.8, recent -> 0.4)
    # Total SUPPORTS = 1.3
    # 1 Tier 2 REFUTES (weight 0.75, conf 0.8, recent -> 0.6)
    # Net Score = 1.3 - 0.6 = 0.7
    evidence = [
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Support quote from fact-checker",
            source_url="https://boomlive.in/test",
            domain_tier=1,
            publish_date="2023-11-01",
            nli_label="SUPPORTS",
            nli_confidence=0.9,
        ),
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Support quote from news",
            source_url="https://reuters.com/test",
            domain_tier=3,
            publish_date="2023-10-15",
            nli_label="SUPPORTS",
            nli_confidence=0.8,
        ),
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Refuting quote from government source",
            source_url="https://pib.gov.in/test",
            domain_tier=2,
            publish_date="2023-12-01",
            nli_label="REFUTES",
            nli_confidence=0.8,
        ),
    ]

    score = calculate_sub_claim_score(evidence, reference_date=fixed_ref_date)
    assert score == pytest.approx(0.70, abs=0.01)


def test_neutral_items_contribute_zero():
    """Verify that NEUTRAL items contribute exactly 0.0 to the score."""
    evidence = [
        EvidenceItem(
            sub_claim_id="sc_1",
            quote="Neutral background quote",
            source_url="https://example.com/neutral",
            domain_tier=1,
            nli_label="NEUTRAL",
            nli_confidence=0.99,
        )
    ]
    score = calculate_sub_claim_score(evidence)
    assert score == 0.0


def test_recency_decay_discounts_older_evidence():
    """Verify that evidence older than 1 year is discounted."""
    fixed_ref_date = datetime(2024, 6, 1, tzinfo=timezone.utc)

    recent_decay = calculate_recency_decay("2024-01-01", reference_date=fixed_ref_date)
    assert recent_decay == 1.0  # ~5 months old <= 365 days

    older_decay = calculate_recency_decay("2022-01-01", reference_date=fixed_ref_date)
    assert older_decay == 0.85  # ~2.5 years old > 365 days

    very_old_decay = calculate_recency_decay("2018-01-01", reference_date=fixed_ref_date)
    assert very_old_decay == 0.70  # > 3 years old


def test_tier_credibility_weighting():
    """Verify Tier 1 curated fact-check outranks Tier 4 general web by 4x."""
    assert TIER_WEIGHTS[1] == 1.00
    assert TIER_WEIGHTS[2] == 0.75
    assert TIER_WEIGHTS[3] == 0.50
    assert TIER_WEIGHTS[4] == 0.25

    t1_ev = [EvidenceItem(sub_claim_id="sc_1", quote="T1", source_url="https://a.com", domain_tier=1, nli_label="SUPPORTS", nli_confidence=1.0)]
    t4_ev = [EvidenceItem(sub_claim_id="sc_1", quote="T4", source_url="https://b.com", domain_tier=4, nli_label="SUPPORTS", nli_confidence=1.0)]

    assert calculate_sub_claim_score(t1_ev) == 1.0
    assert calculate_sub_claim_score(t4_ev) == 0.25


# ---------------------------------------------------------------------------
# Part 2 Tests: Thresholds, Sub-claim Verdicts, and Aggregation
# ---------------------------------------------------------------------------
def test_sub_claim_verdicts_thresholding():
    """Verify threshold logic: score >= 0.60 -> TRUE; score <= -0.60 -> FALSE."""
    # Decisive FALSE
    false_ev = [
        EvidenceItem(
            sub_claim_id="sc_false",
            quote="Definitive debunk quote",
            source_url="https://boomlive.in/debunk",
            domain_tier=1,
            nli_label="REFUTES",
            nli_confidence=0.95,
        ),
        EvidenceItem(
            sub_claim_id="sc_false",
            quote="Second refutation",
            source_url="https://altnews.in/debunk",
            domain_tier=1,
            nli_label="REFUTES",
            nli_confidence=0.90,
        ),
    ]
    res_false = determine_sub_claim_verdict("sc_false", "Drinking papaya seeds cures dengue", false_ev)
    assert res_false.verdict == "FALSE"
    assert res_false.score <= FALSE_THRESHOLD
    assert res_false.confidence >= 0.85

    # Decisive TRUE
    true_ev = [
        EvidenceItem(
            sub_claim_id="sc_true",
            quote="Definitive confirmation quote",
            source_url="https://isro.gov.in/landing",
            domain_tier=2,
            nli_label="SUPPORTS",
            nli_confidence=0.95,
        ),
        EvidenceItem(
            sub_claim_id="sc_true",
            quote="Corroboration from NASA",
            source_url="https://nasa.gov/lunar",
            domain_tier=2,
            nli_label="SUPPORTS",
            nli_confidence=0.90,
        ),
    ]
    res_true = determine_sub_claim_verdict("sc_true", "ISRO landed Chandrayaan-3", true_ev)
    assert res_true.verdict == "TRUE"
    assert res_true.score >= TRUE_THRESHOLD
    assert res_true.confidence >= 0.80


def test_abstention_on_obscure_claims():
    """
    Test epistemic abstention:
    An obscure claim with 0 evidence or 1 weak evidence below threshold
    MUST yield UNVERIFIED, proving the system refuses to answer when evidence is thin.
    """
    # Case A: 0 evidence
    res_empty = determine_sub_claim_verdict("sc_obscure_1", "Secret alien base in Thar desert", [])
    assert res_empty.verdict == "UNVERIFIED"
    assert res_empty.confidence == 0.0

    # Case B: 1 weak Tier 4 evidence with low confidence
    weak_ev = [
        EvidenceItem(
            sub_claim_id="sc_obscure_2",
            quote="A blog mentions mysterious lights in Rajasthan",
            source_url="https://randomblog.com/ufo",
            domain_tier=4,
            nli_label="SUPPORTS",
            nli_confidence=0.55,
        )
    ]
    # score = 0.25 * 0.55 = 0.1375 < ABSTENTION_SCORE_THRESHOLD (0.35) and count < 2
    res_weak = determine_sub_claim_verdict("sc_obscure_2", "Secret alien base in Thar desert", weak_ev)
    assert res_weak.verdict == "UNVERIFIED"

    # Aggregating all unverified sub-claims must produce overall UNVERIFIED with is_abstained=True
    overall_v, overall_c, _, is_abstained = aggregate_verdicts(
        "Alien base in Thar desert", [res_empty, res_weak]
    )
    assert overall_v == "UNVERIFIED"
    assert is_abstained is True


def test_aggregation_rules():
    """
    Test overall composite aggregation rules:
    - Any high-confidence FALSE sub-claim makes composite claim FALSE
    - Mixed results make composite claim PARTIALLY TRUE
    - All TRUE sub-claims make composite claim TRUE
    """
    # 1. Composite headline with 1 FALSE sub-claim (WHO green tea hoax saving 50k lives)
    sc_v_false = SubClaimVerdict(
        sub_claim_id="sc_1",
        sub_claim="WHO confirmed green tea cures COVID",
        score=-1.2,
        verdict="FALSE",
        confidence=0.92,
    )
    sc_v_true = SubClaimVerdict(
        sub_claim_id="sc_2",
        sub_claim="Green tea contains polyphenols",
        score=0.8,
        verdict="TRUE",
        confidence=0.85,
    )
    v_agg, c_agg, _, is_abst = aggregate_verdicts(
        "WHO confirms green tea cures COVID saving 50,000 lives",
        [sc_v_false, sc_v_true],
    )
    assert v_agg == "FALSE"
    assert c_agg >= 0.90
    assert is_abst is False

    # 2. All TRUE sub-claims
    sc_v_true2 = SubClaimVerdict(
        sub_claim_id="sc_3",
        sub_claim="ISRO launched Vikram lander",
        score=1.1,
        verdict="TRUE",
        confidence=0.90,
    )
    v_true_agg, c_true_agg, _, _ = aggregate_verdicts(
        "ISRO launched Vikram lander and confirmed landing",
        [sc_v_true, sc_v_true2],
    )
    assert v_true_agg == "TRUE"
    assert c_true_agg >= 0.85


# ---------------------------------------------------------------------------
# Part 3 Tests: The LLM Explanation & End-to-End Orchestrator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_judge_evaluate_claim_end_to_end():
    """
    Test end-to-end judge_evaluate_claim function with real composite claim,
    sub-claims, and evidence items.
    """
    raw_claim = "WHO officially confirms green tea cures COVID-19 in 48 hours, saving 50,000 lives in India"
    sub_claims = [
        SubClaim(id="sc_1", text="WHO officially confirmed green tea cures COVID-19 in 48 hours", type="attribution"),
        SubClaim(id="sc_2", text="Green tea consumption saved 50,000 lives in India", type="statistical_quantity"),
    ]
    evidence = [
        EvidenceItem(
            sub_claim_id="sc_1",
            sub_claim="WHO officially confirmed green tea cures COVID-19 in 48 hours",
            quote="The WHO Regional Office clarified that this viral message is fabricated; no such confirmation was issued.",
            source_url="https://boomlive.in/who-green-tea",
            domain="boomlive.in",
            domain_tier=1,
            curated=True,
            publish_date="2021-05-10",
            nli_label="REFUTES",
            nli_confidence=0.98,
        ),
        EvidenceItem(
            sub_claim_id="sc_2",
            sub_claim="Green tea consumption saved 50,000 lives in India",
            quote="Health authorities report zero clinical data indicating herbal tea reduced viral mortality by 50,000.",
            source_url="https://altnews.in/green-tea-covid",
            domain="altnews.in",
            domain_tier=1,
            curated=True,
            publish_date="2021-05-12",
            nli_label="REFUTES",
            nli_confidence=0.95,
        ),
    ]

    response = await judge_evaluate_claim(
        raw_claim=raw_claim,
        sub_claims=sub_claims,
        evidence_items=evidence,
        generate_explanation=True,
    )

    assert isinstance(response, JudgeVerdictResponse)
    assert response.overall_verdict == "FALSE"
    assert response.overall_confidence >= 0.70
    assert response.is_abstained is False
    assert len(response.sub_claim_verdicts) == 2
    assert response.sub_claim_verdicts[0].verdict == "FALSE"
    assert response.sub_claim_verdicts[1].verdict == "FALSE"
    assert len(response.explanation) > 50
    assert "https://boomlive.in/who-green-tea" in response.key_citations


@pytest.mark.asyncio
async def test_judge_abstention_end_to_end():
    """
    Test judge_evaluate_claim on an obscure claim where retrieval returns zero evidence.
    Must output UNVERIFIED, is_abstained=True, and an explanatory justification.
    """
    obscure_claim = "Secret subterranean cricket tournament held inside Ajanta Caves in 1912"
    sub_claims = [
        SubClaim(id="sc_obs_1", text="Subterranean cricket tournament held inside Ajanta Caves in 1912", type="factual_event")
    ]

    response = await judge_evaluate_claim(
        raw_claim=obscure_claim,
        sub_claims=sub_claims,
        evidence_items=[],
        generate_explanation=True,
    )

    assert response.overall_verdict == "UNVERIFIED"
    assert response.is_abstained is True
    assert response.overall_confidence == 0.0
    assert "abstained" in response.explanation.lower() or "unverified" in response.explanation.lower()


# ---------------------------------------------------------------------------
# Test 4: FastAPI /api/judge Endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fastapi_judge_endpoint():
    """Verify that FastAPI /api/judge responds with status 200 and deterministic verdict."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    payload = {
        "raw_claim": "WHO confirms green tea cures COVID-19",
        "sub_claims": [
            {"id": "sc_1", "text": "WHO confirms green tea cures COVID-19", "type": "attribution"}
        ],
        "evidence": [
            {
                "sub_claim_id": "sc_1",
                "quote": "WHO officially clarified that no herbal tea cures COVID-19.",
                "source_url": "https://who.int/news",
                "domain_tier": 1,
                "nli_label": "REFUTES",
                "nli_confidence": 0.95,
            },
            {
                "sub_claim_id": "sc_1",
                "quote": "Fact check confirms WHO issued no advisory stating green tea cures COVID.",
                "source_url": "https://boomlive.in/check",
                "domain_tier": 1,
                "nli_label": "REFUTES",
                "nli_confidence": 0.90,
            },
        ],
        "generate_explanation": False,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        resp = await client.post("/api/judge", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_verdict"] == "FALSE"
        assert data["overall_confidence"] >= 0.70
        assert data["is_abstained"] is False
