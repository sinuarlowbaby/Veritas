import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.database import get_db, SessionLocal
from app.models.db_models import UserORM
from app.services.auth_service import hash_password, verify_password, create_access_token, decode_access_token
from app.services.job_store import get_job_store


@pytest.fixture(autouse=True)
def clean_database():
    session = SessionLocal()
    session.query(UserORM).delete()
    session.commit()
    session.close()

    job_store = get_job_store()
    job_store.clear()
    yield
    job_store.clear()


def test_password_hashing():
    pwd = "SecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert "$" in hashed
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_lifecycle():
    token = create_access_token(user_id=42, username="audit_lead")
    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["username"] == "audit_lead"
    assert "exp" in decoded

    # Invalid token check
    assert decode_access_token("fake.token.value") is None


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register new user
        reg_resp = await ac.post(
            "/api/auth/register",
            json={
                "username": "editor_jane",
                "email": "jane@veritas.org",
                "password": "SecurePassword123",
            },
        )
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        assert reg_data["user"]["username"] == "editor_jane"
        assert reg_data["user"]["email"] == "jane@veritas.org"

        # 2. Duplicate registration rejected
        dup_resp = await ac.post(
            "/api/auth/register",
            json={
                "username": "editor_jane",
                "email": "jane2@veritas.org",
                "password": "SecurePassword123",
            },
        )
        assert dup_resp.status_code == 400

        # 3. Login with credentials
        login_resp = await ac.post(
            "/api/auth/login",
            json={
                "username_or_email": "jane@veritas.org",
                "password": "SecurePassword123",
            },
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        token = login_data["access_token"]

        # 4. Access /api/auth/me with Bearer token
        me_resp = await ac.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "editor_jane"

        # 5. Access /api/auth/me without token -> 401
        unauth_resp = await ac.get("/api/auth/me")
        assert unauth_resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_device_history_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create User A
        resp_a = await ac.post(
            "/api/auth/register",
            json={"username": "user_a", "email": "a@veritas.org", "password": "Password123"},
        )
        token_a = resp_a.json()["access_token"]
        user_a_id = resp_a.json()["user"]["id"]

        # Create User B
        resp_b = await ac.post(
            "/api/auth/register",
            json={"username": "user_b", "email": "b@veritas.org", "password": "Password123"},
        )
        token_b = resp_b.json()["access_token"]
        user_b_id = resp_b.json()["user"]["id"]

        # Create completed audit for User A in JobStore
        job_store = get_job_store()
        job_store.create_cached_job(
            job_id="job_user_a_1",
            raw_claim="Papaya leaf extract cures dengue fever",
            claim_hash="hash_a",
            cached_result={"verdict": "FALSE", "confidence": 0.98},
            latency_ms=1.5,
            user_id=user_a_id,
        )

        # Create completed audit for User B in JobStore
        job_store.create_cached_job(
            job_id="job_user_b_1",
            raw_claim="Moon landing was staged in Hollywood",
            claim_hash="hash_b",
            cached_result={"verdict": "FALSE", "confidence": 0.99},
            latency_ms=1.5,
            user_id=user_b_id,
        )

        # User A checks history -> only sees job_user_a_1
        hist_a = await ac.get(
            "/api/history",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert hist_a.status_code == 200
        items_a = hist_a.json()
        assert len(items_a) == 1
        assert items_a[0]["job_id"] == "job_user_a_1"

        # User B checks history -> only sees job_user_b_1
        hist_b = await ac.get(
            "/api/history",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert hist_b.status_code == 200
        items_b = hist_b.json()
        assert len(items_b) == 1
        assert items_b[0]["job_id"] == "job_user_b_1"
