import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.feedback_store import get_feedback_store


@pytest.fixture(autouse=True)
def clean_feedback_store():
    store = get_feedback_store()
    store.clear()
    yield
    store.clear()


@pytest.mark.asyncio
async def test_feedback_store_direct_methods():
    store = get_feedback_store()
    fb1 = store.add_feedback(
        job_id="job_test_001",
        rating="thumbs_down",
        verdict="FALSE",
        comment="The tax policy applies only to state taxes, not federal.",
    )
    assert fb1["id"].startswith("fb_")
    assert fb1["job_id"] == "job_test_001"
    assert fb1["rating"] == "thumbs_down"
    assert fb1["verdict"] == "FALSE"
    assert "tax policy" in fb1["comment"]

    fb2 = store.add_feedback(
        job_id="job_test_002",
        rating="thumbs_up",
        verdict="TRUE",
        comment="Spot on analysis with government sources.",
    )
    assert fb2["rating"] == "thumbs_up"

    all_items = store.list_feedback()
    assert len(all_items) == 2

    # Filter by thumbs_down (flagged reviews)
    down_items = store.list_feedback(rating="thumbs_down")
    assert len(down_items) == 1
    assert down_items[0]["job_id"] == "job_test_001"


@pytest.mark.asyncio
async def test_api_post_and_get_feedback():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit thumbs_down feedback
        payload = {
            "job_id": "job_123456",
            "rating": "thumbs_down",
            "verdict": "FALSE",
            "comment": "The quote cited from the gazette notification was misinterpreted.",
        }
        res = await client.post("/api/feedback", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["job_id"] == "job_123456"
        assert data["rating"] == "thumbs_down"
        assert data["verdict"] == "FALSE"
        assert "misinterpreted" in data["comment"]
        assert "id" in data
        assert "created_at" in data

        # Submit thumbs_up feedback
        res_up = await client.post(
            "/api/feedback",
            json={
                "job_id": "job_789012",
                "rating": "thumbs_up",
                "verdict": "TRUE",
                "comment": "Accurate citations.",
            },
        )
        assert res_up.status_code == 201

        # Query all feedback via admin endpoint
        res_list = await client.get("/api/feedback")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] == 2
        assert len(list_data["items"]) == 2

        # Query flagged feedback (thumbs_down only)
        res_flags = await client.get("/api/feedback?rating=thumbs_down")
        assert res_flags.status_code == 200
        flags_data = res_flags.json()
        assert flags_data["total"] == 1
        assert flags_data["items"][0]["job_id"] == "job_123456"
        assert flags_data["items"][0]["rating"] == "thumbs_down"
