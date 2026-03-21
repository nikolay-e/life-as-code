import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def app():
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
        assert "database" in data
        assert "timestamp" in data

    def test_health_has_timestamp(self, client):
        response = client.get("/health")
        data = response.get_json()
        assert data["timestamp"] is not None

    def test_health_does_not_expose_version(self, client):
        response = client.get("/health")
        data = response.get_json()
        assert "version" not in data
        assert "build_date" not in data
        assert "commit" not in data


class TestCSRFProtection:
    def test_api_post_without_csrf_header_rejected(self, client):
        response = client.post("/api/auth/login", json={"username": "a", "password": "b"})  # NOSONAR
        assert response.status_code == 403

    def test_api_post_with_csrf_header_allowed(self, client):
        response = client.post(
            "/api/auth/login",
            json={"username": "a", "password": "b"},  # NOSONAR
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code != 403

    def test_api_get_without_csrf_header_allowed(self, client):
        response = client.get("/api/analytics", query_string={"mode": "recent"})
        assert response.status_code != 403


class TestAuthRequired:
    def test_unauthenticated_api_returns_401(self, client):
        response = client.get("/api/analytics", query_string={"mode": "recent"})
        assert response.status_code in (401, 302)

    def test_sync_status_unauthenticated(self, client):
        response = client.get("/api/sync/status")
        assert response.status_code in (401, 302)
