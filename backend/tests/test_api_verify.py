import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.job_store import get_job_store
from app.models.schemas import EvidenceItem, JudgeVerdictResponse, SubClaimVerdict



@pytest.fixture(autouse=True)
def clean_job_store():
    store = get_job_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def mock_pipeline_result_false():
    res = JudgeVerdictResponse(
        raw_claim="Finance Ministry eliminates all income tax for citizens over 60 starting April 1",
        overall_verdict="FALSE",
        overall_confidence=0.998,
        overall_score=-0.998,
        is_abstained=False,
        sub_claim_verdicts=[
            SubClaimVerdict(
                sub_claim_id="subclaim_1",
                sub_claim="Income tax eliminated for citizens over 60",
                score=-0.998,
                verdict="FALSE",
                confidence=0.998,
                evidence_count=5,
                supporting_count=0,
                refuting_count=4,
                neutral_count=1,
            )
        ],
        explanation="Official Finance Ministry documentation confirms tax slabs remain active for senior citizens.",
        key_citations=["https://incometax.gov.in/rules"],
        evidence=[
            EvidenceItem(
                evidence_id="ev_001",
                sub_claim_id="subclaim_1",
                sub_claim="Income tax eliminated for citizens over 60",
                quote="Income tax slabs and rates for senior citizens (aged 60-80 years) continue as per current laws.",
                source_url="https://incometax.gov.in/rules",
                domain="incometax.gov.in",
                domain_tier=2,
                nli_label="REFUTES",
                nli_confidence=0.999,
                retrieved_by="skeptic",
            )
        ],
        tokens_used=640,
    )
    return res


@pytest.fixture
def mock_pipeline_result_abstained():
    return JudgeVerdictResponse(
        raw_claim="Astronomers discover subterranean crystalline city on Jupiter's moon Ganymede",
        overall_verdict="UNVERIFIED",
        overall_confidence=0.0,
        overall_score=0.0,
        is_abstained=True,
        sub_claim_verdicts=[],
        explanation="No reliable evidence retrieved to evaluate this assertion.",
        key_citations=[],
        tokens_used=420,
    )


@pytest.mark.asyncio
async def test_api_verify_async_job_and_polling(mock_pipeline_result_false):
    async def fake_run_pipeline(raw_claim, status_callback=None, generate_explanation=True, **kwargs):
        if status_callback:
            status_callback("harvesting_evidence")
            status_callback("nli_verification")
        await asyncio.sleep(0.05)
        return mock_pipeline_result_false

    with patch("app.main.run_verification_pipeline", side_effect=fake_run_pipeline):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            claim_text = "Finance Ministry eliminates all income tax for citizens over 60 starting April 1"

            # Step 1: Enqueue async verification job
            enqueue_resp = await client.post(
                "/api/verify",
                json={
                    "claim": claim_text,
                    "generate_explanation": True,
                },
            )
            assert enqueue_resp.status_code == 202
            enqueue_data = enqueue_resp.json()
            assert "job_id" in enqueue_data
            job_id = enqueue_data["job_id"]
            assert enqueue_data["status"] in ("pending", "processing")

            # Step 2: Poll job until completion
            completed = False
            final_job_data = None

            for _ in range(30):
                await asyncio.sleep(0.05)
                poll_resp = await client.get(f"/api/verify/{job_id}")
                assert poll_resp.status_code == 200
                poll_data = poll_resp.json()
                if poll_data["status"] == "completed":
                    completed = True
                    final_job_data = poll_data
                    break
                elif poll_data["status"] == "failed":
                    pytest.fail(f"Job failed with error: {poll_data.get('error')}")

            assert completed is True
            assert final_job_data is not None
            assert final_job_data["status"] == "completed"
            assert final_job_data["stage"] == "completed"
            assert final_job_data["completed_at"] is not None
            assert final_job_data["latency_ms"] is not None
            assert final_job_data["token_count"] == 640

            # Verify frontend dumb-renderer dictionary shape
            result = final_job_data["result"]
            assert result is not None
            assert result["verdict"] == "FALSE"
            assert result["confidence"] > 0.70
            assert "Finance Ministry" in result["explanation"]
            assert len(result["sub_claims"]) == 1
            assert result["sub_claims"][0]["verdict"] == "FALSE"

            # Check evidence list with quotes, URLs, and NLI labels
            assert "evidence" in result
            assert len(result["evidence"]) >= 1
            ev_first = result["evidence"][0]
            assert "quote" in ev_first
            assert "source_url" in ev_first
            assert ev_first["nli_label"] == "REFUTES"
            assert ev_first["domain_tier"] == 2


@pytest.mark.asyncio
async def test_api_verify_caching(mock_pipeline_result_false):
    """
    Submitting the exact same claim twice must return instantly from cache on the second request.
    """
    call_count = 0

    async def fake_run_pipeline(raw_claim, status_callback=None, generate_explanation=True, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return mock_pipeline_result_false

    with patch("app.main.run_verification_pipeline", side_effect=fake_run_pipeline):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            claim_text = "WHO confirms green tea cures COVID-19 in 48 hours for demo caching test"

            # 1. First run -> Enqueued and processed
            resp1 = await client.post("/api/verify", json={"claim": claim_text})
            assert resp1.status_code == 202
            data1 = resp1.json()
            job1_id = data1["job_id"]
            assert data1["cached"] is False

            # Wait for job1 to complete
            for _ in range(25):
                await asyncio.sleep(0.05)
                poll = await client.get(f"/api/verify/{job1_id}")
                if poll.json()["status"] == "completed":
                    break

            # 2. Second run with IDENTICAL claim (different case / extra spaces to test normalization)
            claim_text_variation = "  who confirms green tea cures covid-19 in 48 hours for demo caching test!  "
            resp2 = await client.post("/api/verify", json={"claim": claim_text_variation})
            assert resp2.status_code == 202
            data2 = resp2.json()

            # The second response should arrive instantly from cache in milliseconds!
            assert data2["cached"] is True
            assert data2["status"] == "completed"
            assert data2["result"] is not None
            assert data2["result"]["verdict"] == "FALSE"
            assert data2["latency_ms"] < 50.0  # Served in milliseconds!

            # The background pipeline should only have run ONCE!
            assert call_count == 1


@pytest.mark.asyncio
async def test_api_verify_job_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/verify/non_existent_job_12345")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_verify_sync(mock_pipeline_result_abstained):
    with patch("app.main.run_verification_pipeline", AsyncMock(return_value=mock_pipeline_result_abstained)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/verify/sync",
                json={
                    "claim": "Astronomers discover subterranean crystalline city on Jupiter's moon Ganymede",
                    "generate_explanation": True,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["overall_verdict"] == "UNVERIFIED"
            assert data["is_abstained"] is True
