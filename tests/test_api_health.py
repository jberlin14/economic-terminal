"""Tests for health API endpoints."""

import pytest


class TestHealthEndpoints:
    def test_basic_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_detailed_health(self, client):
        response = client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "warning", "degraded")
        assert "components" in data
        assert "database" in data["components"]

    def test_module_health(self, client):
        response = client.get("/api/health/modules")
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
        assert isinstance(data["modules"], list)

    def test_refresh_starts(self, client):
        response = client.post("/api/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("started", "already_running")

    def test_refresh_status(self, client):
        response = client.get("/api/refresh/status")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert isinstance(data["running"], bool)
