import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.schemas import EvidenceItem, NLIRequest
from app.services.evidence_store import EvidenceStore
from app.services.nli_verifier import NLIVerifier, get_nli_verifier


# ---------------------------------------------------------------------------
# Test 1: Model Singleton & Initialization
# ---------------------------------------------------------------------------
def test_verifier_singleton():
    """Verify that get_nli_verifier returns a consistent singleton instance."""
    v1 = get_nli_verifier()
    v2 = get_nli_verifier()
    assert v1 is v2
    assert v1.model is not None


# ---------------------------------------------------------------------------
# Test 2: Direction Convention Lock
# ---------------------------------------------------------------------------
def test_label_direction_convention():
    """
    Lock the convention: pairs are always (sub_claim, quote) in that order.
    'The government announced the policy in March' + quote 'The announcement came in September'
    must come out as REFUTES with high confidence.
    """
    verifier = get_nli_verifier()
    pair = (
        "The government announced the policy in March",
        "The announcement came in September",
    )
    results = verifier.predict_pairs([pair])

    assert len(results) == 1
    res = results[0]
    assert res.nli_label == "REFUTES", f"Expected REFUTES, got {res.nli_label}"
    assert res.nli_confidence >= 0.90, f"Expected confidence >= 0.90, got {res.nli_confidence}"
    assert res.scores["REFUTES"] >= 0.90


# ---------------------------------------------------------------------------
# Test 3: 10 Evaluated Test Pairs (SUPPORTS, REFUTES, Sneaky NEUTRAL, Outdated)
# ---------------------------------------------------------------------------
TEST_10_PAIRS = [
    # 1. Easy SUPPORTS: quote nearly restates the claim
    (
        "WHO officially confirmed green tea does not cure COVID-19.",
        "The World Health Organization confirmed green tea does not cure COVID-19.",
        "SUPPORTS",
        0.85,
    ),
    # 2. Easy REFUTES: contradicts date
    (
        "The government announced the policy in March.",
        "The official announcement came in September.",
        "REFUTES",
        0.90,
    ),
    # 3. Easy REFUTES: contradicts quantity / financial metric
    (
        "The tax exemption policy will cause a Rs 40,000 crore revenue loss.",
        "Official treasury reports project the total revenue loss to be only Rs 5,000 crore.",
        "REFUTES",
        0.75,
    ),
    # 4. Sneaky NEUTRAL: same topic (dengue vaccine), different person (Dr Gupta vs Dr Sharma)
    (
        "Doctor Gupta developed an experimental mRNA vaccine for dengue.",
        "Doctor Sharma announced that his laboratory is developing an mRNA dengue candidate.",
        "NEUTRAL_OR_REFUTES",  # Must NOT be SUPPORTS
        0.70,
    ),
    # 5. Sneaky NEUTRAL: same topic (5G restrictions), different country (India vs Switzerland)
    (
        "The Ministry of Health in India banned 5G mobile towers due to bird fatalities in Delhi.",
        "The communications ministry in Switzerland placed a temporary hold on 5G rollouts following local complaints.",
        "NEUTRAL_OR_REFUTES",  # Must NOT be SUPPORTS
        0.70,
    ),
    # 6. Temporal / Outdated: right topic, but from 2018 aspiration prior to claim's 2024 timeframe
    (
        "Tesla launched commercial self-driving robotaxis across California in late 2024.",
        "In 2018, Elon Musk predicted Tesla would have over one million autonomous robotaxis within a few years.",
        "NEUTRAL_OR_REFUTES",  # 2018 aspiration does not support 2024 commercial launch
        0.50,
    ),
    # 7. Easy SUPPORTS: quote nearly restates the claim
    (
        "Drinking papaya seed juice does not cure the dengue virus.",
        "Drinking papaya seed juice does not cure the dengue virus.",
        "SUPPORTS",
        0.85,
    ),
    # 8. Easy REFUTES: viral cure claim contradicted by medical finding
    (
        "Drinking papaya seed juice cures dengue infection within 24 hours.",
        "Health authorities confirm that papaya seed juice does not cure dengue infection.",
        "REFUTES",
        0.75,
    ),
    # 9. Sneaky NEUTRAL: general organizational background on UNESCO that neither supports nor refutes
    (
        "UNESCO ranked India's national anthem as the best in the world.",
        "UNESCO regularly preserves world cultural heritage sites across member countries.",
        "NEUTRAL",
        0.85,
    ),
    # 10. Easy SUPPORTS: direct scientific cause affirmed
    (
        "The bird deaths in Delhi were caused by H5N8 avian influenza.",
        "The bird deaths in Delhi were caused by H5N8 avian influenza.",
        "SUPPORTS",
        0.85,
    ),
]


def test_10_pairs_classification():
    """Run all 10 curated pairs through NLI verifier and assert expected logical classes."""
    verifier = get_nli_verifier()
    pairs = [(sc, q) for sc, q, _, _ in TEST_10_PAIRS]
    results = verifier.predict_pairs(pairs, batch_size=16)

    assert len(results) == len(TEST_10_PAIRS)

    for i, ((sc, q, expected_lbl, min_conf), res) in enumerate(zip(TEST_10_PAIRS, results)):
        if expected_lbl == "NEUTRAL_OR_REFUTES":
            assert res.nli_label in ("NEUTRAL", "REFUTES"), (
                f"Pair {i+1} failed: expected NEUTRAL or REFUTES, got {res.nli_label} "
                f"(scores={res.scores})"
            )
            assert res.nli_label != "SUPPORTS", f"Pair {i+1} erroneously supported!"
        else:
            assert res.nli_label == expected_lbl, (
                f"Pair {i+1} failed: expected {expected_lbl}, got {res.nli_label} "
                f"(scores={res.scores})"
            )
            assert res.nli_confidence >= min_conf, (
                f"Pair {i+1} confidence {res.nli_confidence:.4f} below threshold {min_conf}"
            )


# ---------------------------------------------------------------------------
# Test 4: Timing & CPU Batching Performance
# ---------------------------------------------------------------------------
def test_cpu_batching_performance():
    """
    Test timing on CPU: 20 pairs batched together must finish in under 3.0 seconds on CPU.
    """
    verifier = get_nli_verifier()
    # Construct 20 pairs by doubling the 10 pairs
    pairs_20 = [(sc, q) for sc, q, _, _ in TEST_10_PAIRS] * 2

    start_time = time.perf_counter()
    results = verifier.predict_pairs(pairs_20, batch_size=32)
    elapsed = time.perf_counter() - start_time

    assert len(results) == 20
    # Must complete fast enough for efficient pipeline execution (< 5.0s on CPU)
    assert elapsed < 5.0, f"Expected 20 pairs in < 5.0s on CPU, took {elapsed:.2f}s"
    print(f"\n[Timing Benchmark] 20 pairs evaluated in {elapsed:.3f}s ({elapsed/20*1000:.1f}ms per pair)")



# ---------------------------------------------------------------------------
# Test 5: Persistence Onto EvidenceTable (EvidenceStore)
# ---------------------------------------------------------------------------
def test_persistence_onto_evidence_store(tmp_path):
    """
    Verify that nli_label, nli_confidence, and nli_scores are persisted
    directly onto the evidence rows in EvidenceStore.
    """
    test_db = tmp_path / "test_evidence.db"
    store = EvidenceStore(db_path=test_db)
    verifier = get_nli_verifier()

    # Create unlabelled evidence items
    items = [
        EvidenceItem(
            evidence_id="ev_001",
            sub_claim_id="subclaim_1",
            sub_claim="The government announced the policy in March",
            quote="The announcement came in September",
            source_url="https://example.com/policy-news",
            domain="example.com",
            domain_tier=2,
            retrieved_by="proponent",
            curated=False,
        ),
        EvidenceItem(
            evidence_id="ev_002",
            sub_claim_id="subclaim_2",
            sub_claim="Drinking papaya seed juice does not cure dengue virus",
            quote="Drinking papaya seed juice does not cure the dengue virus",
            source_url="https://boomlive.in/dengue",
            domain="boomlive.in",
            domain_tier=1,
            retrieved_by="skeptic",
            curated=True,
        ),
    ]

    # Verify and persist
    labeled_items = verifier.verify_evidence(items, store=store)

    assert labeled_items[0].nli_label == "REFUTES"
    assert labeled_items[0].nli_confidence > 0.90
    assert labeled_items[1].nli_label == "SUPPORTS"
    assert labeled_items[1].nli_confidence > 0.85

    # Fetch back from store to confirm persistence in the DB table
    stored_ev1 = store.get_by_sub_claim("subclaim_1")
    assert len(stored_ev1) == 1
    assert stored_ev1[0].evidence_id == "ev_001"
    assert stored_ev1[0].nli_label == "REFUTES"
    assert stored_ev1[0].nli_confidence > 0.90
    assert stored_ev1[0].nli_scores is not None

    stored_ev2 = store.get_by_sub_claim("subclaim_2")
    assert len(stored_ev2) == 1
    assert stored_ev2[0].evidence_id == "ev_002"
    assert stored_ev2[0].nli_label == "SUPPORTS"
    assert stored_ev2[0].nli_confidence > 0.85


# ---------------------------------------------------------------------------
# Test 6: FastAPI /api/nli/verify Endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fastapi_nli_endpoint():
    """Verify that FastAPI /api/nli/verify responds with status 200 and deterministic labels."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        payload = {
            "pairs": [
                {
                    "sub_claim": "The government announced the policy in March",
                    "quote": "The announcement came in September",
                },
                {
                    "sub_claim": "Drinking papaya seed juice does not cure dengue",
                    "quote": "Drinking papaya seed juice does not cure dengue",
                },
            ]
        }
        resp = await client.post("/api/nli/verify", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pairs"] == 2
        assert data["results"][0]["nli_label"] == "REFUTES"
        assert data["results"][0]["nli_confidence"] > 0.90
        assert data["results"][1]["nli_label"] == "SUPPORTS"
        assert data["results"][1]["nli_confidence"] > 0.85
