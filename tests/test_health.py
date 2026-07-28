from fastapi.testclient import TestClient
import uuid
from app.main import app
from app.api.dependencies.services import get_readiness_service
from app.application.services.readiness_service import ReadinessService


class StubReadinessProbe:
    def __init__(self, ready: bool) -> None:
        self.ready = ready

    async def check(self) -> bool:
        return self.ready


def readiness_service(ready: bool) -> ReadinessService:
    return ReadinessService(database_probe=StubReadinessProbe(ready))


app.dependency_overrides[get_readiness_service] = lambda: readiness_service(True)

client = TestClient(app)

def test_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_request_id_middleware():
    response = client.get("/health/live", headers={"X-Request-ID": "test-req-123"})
    assert response.headers["X-Request-ID"] == "test-req-123"


def test_untrusted_request_id_is_replaced_with_server_uuid():
    response = client.get(
        "/health/live",
        headers={"X-Request-ID": "sensitive transcript content"},
    )

    generated_request_id = response.headers["X-Request-ID"]
    assert generated_request_id != "sensitive transcript content"
    assert str(uuid.UUID(generated_request_id)) == generated_request_id

def test_versioned_health_paths_remain_available():
    live_response = client.get("/api/v1/health/live")
    ready_response = client.get("/api/v1/health/ready")

    assert live_response.status_code == 200
    assert ready_response.status_code == 200


def test_ready_returns_503_when_database_is_unavailable():
    original_override = app.dependency_overrides[get_readiness_service]
    app.dependency_overrides[get_readiness_service] = lambda: readiness_service(False)

    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides[get_readiness_service] = original_override

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
