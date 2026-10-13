import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.job_store import get_job_store, compute_claim_hash


@pytest.mark.asyncio
async def test_guest_sync_to_db_and_cache_history():
    job_store = get_job_store()
    job_store.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create a guest audit job without login
        guest_claim = "WHO confirms green tea cures virus in 48 hours"
        guest_job_id = "job_guest_test_001"
        claim_hash = compute_claim_hash(guest_claim)
        
        dummy_result = {
            "claim": guest_claim,
            "verdict": "FALSE",
            "confidence": 0.95,
            "score": -0.92,
            "explanation": "WHO has clarified that green tea does not cure the virus.",
            "sub_claims": [],
            "evidence": [],
        }

        job_store.create_cached_job(
            job_id=guest_job_id,
            raw_claim=guest_claim,
            claim_hash=claim_hash,
            cached_result=dummy_result,
            latency_ms=1.5,
            user_id=None,  # Guest task done without login
            cache_type="exact",
        )

        # Confirm job exists with user_id is None
        initial_job = job_store.get_job(guest_job_id)
        assert initial_job is not None
        assert initial_job["user_id"] is None
        assert initial_job["cached"] is True
        assert initial_job["cache_type"] == "exact"

        # 2. Register and authenticate a new user
        reg_resp = await client.post(
            "/api/auth/register",
            json={
                "username": "guestsyncuser",
                "email": "guestsync@veritas.test",
                "password": "Password123!",
            },
        )
        assert reg_resp.status_code == 201
        auth_data = reg_resp.json()
        token = auth_data["access_token"]
        user_id = auth_data["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Before sync: user history should be empty
        hist_before = await client.get("/api/history", headers=headers)
        assert hist_before.status_code == 200
        assert len(hist_before.json()) == 0

        # 4. Sync guest tasks to the user's database account
        sync_resp = await client.post(
            "/api/history/sync",
            headers=headers,
            json={"job_ids": [guest_job_id]},
        )
        assert sync_resp.status_code == 200
        synced_history = sync_resp.json()
        assert len(synced_history) == 1
        assert synced_history[0]["job_id"] == guest_job_id
        assert synced_history[0]["user_id"] == user_id
        assert synced_history[0]["cached"] is True
        assert synced_history[0]["cache_type"] == "exact"
        assert synced_history[0]["verdict"] == "FALSE"

        # 5. Retrieve specific historical cache-hit job via /api/history/{job_id}
        single_resp = await client.get(f"/api/history/{guest_job_id}", headers=headers)
        assert single_resp.status_code == 200
        single_data = single_resp.json()
        assert single_data["job_id"] == guest_job_id
        assert single_data["cached"] is True
        assert single_data["result"]["verdict"] == "FALSE"
        assert single_data["result"]["claim"] == guest_claim
