"""Tests for credit API endpoints."""

import pytest
from datetime import datetime
from modules.data_storage.schema import CreditSpread


@pytest.fixture
def seed_credit(db_session):
    """Insert test credit spread data."""
    spreads = [
        CreditSpread(
            index_name="US HY",
            spread_bps=350.5,
            timestamp=datetime(2026, 3, 25, 10, 0),
            percentile_90d=45.0
        ),
        CreditSpread(
            index_name="US IG BBB",
            spread_bps=120.0,
            timestamp=datetime(2026, 3, 25, 10, 0),
            percentile_90d=30.0
        ),
    ]
    db_session.add_all(spreads)
    db_session.commit()
    yield


class TestCreditAPI:
    def test_get_spreads_empty(self, client):
        response = client.get("/api/credit/spreads")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_get_spreads_with_data(self, client, seed_credit):
        response = client.get("/api/credit/spreads")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_get_spread_by_index(self, client, seed_credit):
        response = client.get("/api/credit/spreads/US HY")
        assert response.status_code == 200
        data = response.json()
        assert data["index_name"] == "US HY"

    def test_get_spread_case_insensitive(self, client, seed_credit):
        response = client.get("/api/credit/spreads/us hy")
        assert response.status_code == 200

    def test_get_spread_not_found(self, client, seed_credit):
        response = client.get("/api/credit/spreads/NONEXISTENT")
        assert response.status_code == 404

    def test_credit_summary_identifies_hy_ig(self, client, seed_credit):
        response = client.get("/api/credit/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["high_yield"] is not None
        assert data["investment_grade"] is not None
        assert data["market_status"] == "NORMAL"
