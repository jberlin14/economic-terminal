"""Tests for FX API endpoints."""

import pytest
from datetime import datetime
from modules.data_storage.schema import FXRate


@pytest.fixture
def seed_fx(db_session):
    """Insert test FX data."""
    rates = [
        FXRate(
            pair="USD/EUR",
            rate=0.92,
            timestamp=datetime(2026, 3, 25, 10, 0),
            change_1h=0.01,
            change_24h=-0.15,
            change_1w=0.30,
        ),
        FXRate(
            pair="USD/JPY",
            rate=149.5,
            timestamp=datetime(2026, 3, 25, 10, 0),
            change_1h=-0.05,
            change_24h=0.20,
            change_1w=-0.40,
        ),
    ]
    db_session.add_all(rates)
    db_session.commit()
    yield


class TestFXAPI:
    def test_get_rates_empty(self, client):
        response = client.get("/api/fx/rates")
        assert response.status_code == 200

    def test_get_rates_with_data(self, client, seed_fx):
        response = client.get("/api/fx/rates")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 2

    def test_get_rate_by_pair(self, client, seed_fx):
        response = client.get("/api/fx/rates/USD-EUR")
        assert response.status_code == 200

    def test_get_rate_not_found(self, client, seed_fx):
        response = client.get("/api/fx/rates/XXX-YYY")
        assert response.status_code == 404

    def test_top_movers_default(self, client, seed_fx):
        response = client.get("/api/fx/movers")
        assert response.status_code == 200
        data = response.json()
        assert "movers" in data

    def test_top_movers_invalid_period(self, client):
        response = client.get("/api/fx/movers?period=invalid")
        assert response.status_code == 422
