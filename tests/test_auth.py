from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.auth import get_identity_provider, get_db_session
from tests.fake_oidc import FakeGoogleOIDCProvider

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.infrastructure.database.base import Base


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def override_get_db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session

fake_provider = FakeGoogleOIDCProvider()

def override_get_identity_provider():
    return fake_provider

app.dependency_overrides[get_identity_provider] = override_get_identity_provider
app.dependency_overrides[get_db_session] = override_get_db_session

def test_auth_start():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/google/start", follow_redirects=False)
        assert response.status_code == 307
        assert "http://fake.google.auth" in response.headers["location"]

        cookies = response.cookies
        assert "oauth_state" in cookies
        assert "oauth_nonce" in cookies

def test_auth_callback_and_session():
    with TestClient(app) as client:
        start_resp = client.get(
            "/api/v1/auth/google/start", follow_redirects=False
        )
        state = start_resp.cookies.get("oauth_state")

        callback_resp = client.get(
            f"/api/v1/auth/google/callback?code=testcode&state={state}",
            follow_redirects=False,
        )

        assert callback_resp.status_code == 307
        assert callback_resp.headers["location"] == "/"
        assert "app_session" in callback_resp.cookies
        assert "oauth_state" not in callback_resp.cookies

        session_resp = client.get("/api/v1/session")

        assert session_resp.status_code == 200
        assert session_resp.headers["cache-control"] == "no-store"
        data = session_resp.json()
        assert data["message"] == "Authenticated successfully"
        assert data["user"]["primary_email"] == "test@example.com"
        assert data["user"]["display_name"] == "Test User"
        assert isinstance(data["csrf_token"], str)
        assert data["csrf_token"]

        logout_resp = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": data["csrf_token"]},
        )
        assert logout_resp.status_code == 204

        client.cookies.set("app_session", "invalid")
        unauth_resp = client.get("/api/v1/session")
        assert unauth_resp.status_code == 401
