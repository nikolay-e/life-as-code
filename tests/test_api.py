import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def app():
    from cryptography.fernet import Fernet

    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-32chars"  # pragma: allowlist secret
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
    os.environ.setdefault("ADMIN_USERNAME", "admin@test.com")
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-123")

    from app import server

    server.config["TESTING"] = True
    return server


@pytest.fixture
def client(app):
    return app.test_client()


class TestHealthEndpoint:
    def test_health_returns_json(self, client):
        response = client.get("/health")
        data = response.get_json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_has_timestamp(self, client):
        response = client.get("/health")
        data = response.get_json()
        assert data["timestamp"] is not None


class TestAuthRequired:
    def test_unauthenticated_api_returns_401(self, client):
        response = client.get("/api/analytics", query_string={"mode": "recent"})
        assert response.status_code in (401, 302)

    def test_sync_status_unauthenticated(self, client):
        response = client.get("/api/sync/status")
        assert response.status_code in (401, 302)
