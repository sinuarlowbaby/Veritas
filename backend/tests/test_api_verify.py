import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, verification_jobs
from app.models.schemas import JudgeVerdictResponse, SubClaimVerdict


@pytest.fixture
def mock_pipeline_result_false():
    return JudgeVerdictResponse(
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
    )


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
            # Step 1: Enqueue async verification job
            enqueue_resp = await client.post(
                "/api/verify",
                json={
                    "text": "Finance Ministry eliminates all income tax for citizens over 60 starting April 1",
                    "generate_explanation": True,
                },
            )
            assert enqueue_resp.status_code == 202
            enqueue_data = enqueue_resp.json()
            assert "job_id" in enqueue_data
            job_id = enqueue_data["job_id"]
            assert enqueue_data["status"] in ("queued", "processing")

            # Step 2: Poll job until completion
            completed = False
            final_job_data = None

            for _ in range(20):
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

            result = final_job_data["result"]
            assert result["overall_verdict"] == "FALSE"
            assert result["overall_confidence"] > 0.70
            assert len(result["sub_claim_verdicts"]) == 1
            assert "Finance Ministry" in result["explanation"]


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
                    "text": "Astronomers discover subterranean crystalline city on Jupiter's moon Ganymede",
                    "generate_explanation": True,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["overall_verdict"] == "UNVERIFIED"
            assert data["is_abstained"] is True
            assert data["overall_confidence"] == 0.0
