"""Tests for yields API endpoints."""

import pytest
from datetime import datetime
from modules.data_storage.schema import YieldCurve


@pytest.fixture
def seed_yields(db_session):
    """Insert test yield curve data."""
    curve = YieldCurve(
        country="US",
        timestamp=datetime(2026, 3, 25, 10, 0),
        tenor_1m=4.30, tenor_3m=4.35, tenor_6m=4.40,
        tenor_1y=4.20, tenor_2y=4.10, tenor_5y=4.05,
        tenor_10y=4.25, tenor_20y=4.50, tenor_30y=4.55,
        spread_10y2y=15.0, spread_10y3m=-10.0, spread_30y10y=30.0,
    )
    db_session.add(curve)
    db_session.commit()
    yield


class TestYieldsAPI:
    def test_get_curve_empty(self, client):
        # No data seeded — expect 404 since storage returns None and endpoint raises HTTPException
        response = client.get("/api/yields/curve")
        assert response.status_code == 404

    def test_get_curve_with_data(self, client, seed_yields):
        response = client.get("/api/yields/curve")
        assert response.status_code == 200
        data = response.json()
        assert "curve" in data
        assert data["curve"]["10Y"] == 4.25

    def test_spread_history_valid_enum(self, client, seed_yields):
        response = client.get("/api/yields/spread-history?spread=10y2y")
        assert response.status_code == 200

    def test_spread_history_invalid_enum(self, client):
        response = client.get("/api/yields/spread-history?spread=invalid")
        assert response.status_code == 422

    def test_tenor_chart_valid(self, client, seed_yields):
        response = client.get("/api/yields/tenor-chart?tenor=10Y&horizon=1m")
        assert response.status_code == 200

    def test_tenor_chart_invalid_tenor(self, client):
        response = client.get("/api/yields/tenor-chart?tenor=INVALID")
        assert response.status_code == 422

    def test_history_days_validation(self, client):
        # days=0 violates ge=1
        response = client.get("/api/yields/history?days=0")
        assert response.status_code == 422
        # days=366 violates le=365
        response = client.get("/api/yields/history?days=366")
        assert response.status_code == 422
