import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, verification_jobs


@pytest.mark.asyncio
async def test_api_verify_async_job_and_polling():
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

        # Step 2: Poll job until completion or max attempts
        max_attempts = 30
        completed = False
        final_job_data = None

        for _ in range(max_attempts):
            await asyncio.sleep(1.0)
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
        assert final_job_data["result"] is not None
        result = final_job_data["result"]
        assert result["overall_verdict"] == "FALSE"
        assert result["overall_confidence"] > 0.70
        assert len(result["sub_claim_verdicts"]) > 0
        assert len(result["explanation"]) > 20


@pytest.mark.asyncio
async def test_api_verify_job_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/verify/non_existent_job_12345")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_verify_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/verify/sync",
            json={
                "text": "Astronomers discover subterranean crystalline city on Jupiter's moon Ganymede dating back 400,000 years",
                "generate_explanation": True,
            },
            timeout=30.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_verdict"] == "UNVERIFIED"
        assert data["is_abstained"] is True
