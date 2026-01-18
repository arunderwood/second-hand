"""Tests for FastAPI application endpoints."""

from fastapi.testclient import TestClient


class TestDashboardEndpoint:
    """Tests for the dashboard endpoint."""

    def test_get_dashboard_returns_200(self, client: TestClient) -> None:
        """GET / should return 200 status code."""
        response = client.get("/")
        assert response.status_code == 200

    def test_get_dashboard_returns_html(self, client: TestClient) -> None:
        """GET / should return HTML content type."""
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_get_dashboard_contains_title(self, client: TestClient) -> None:
        """GET / should return page with second-hand title."""
        response = client.get("/")
        assert "second-hand" in response.text


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """GET /health should return 200 status code."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, client: TestClient) -> None:
        """GET /health should return healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_includes_version(self, client: TestClient) -> None:
        """GET /health should include version in response."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"


class TestNotFoundHandler:
    """Tests for 404 error handling."""

    def test_not_found_returns_404(self, client: TestClient) -> None:
        """Non-existent path should return 404 status code."""
        response = client.get("/nonexistent-path")
        assert response.status_code == 404

    def test_not_found_returns_html(self, client: TestClient) -> None:
        """404 response should be HTML, not JSON."""
        response = client.get("/nonexistent-path")
        assert "text/html" in response.headers["content-type"]

    def test_not_found_contains_error_message(self, client: TestClient) -> None:
        """404 page should contain an error message."""
        response = client.get("/nonexistent-path")
        assert "404" in response.text or "not found" in response.text.lower()
