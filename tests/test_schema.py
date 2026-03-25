"""Tests for schema model serialization."""

import pytest
from datetime import datetime
from modules.data_storage.schema import FXRate, YieldCurve, CreditSpread


class TestFXRateModel:
    def test_to_dict(self):
        rate = FXRate(
            pair="USD/EUR", rate=0.92,
            timestamp=datetime(2026, 3, 25, 10, 0),
            change_1h=0.01, change_24h=-0.15,
        )
        d = rate.to_dict()
        assert d["pair"] == "USD/EUR"
        assert d["rate"] == 0.92
        assert "2026-03-25" in d["timestamp"]
        assert d["sparkline"] == []

    def test_to_dict_null_timestamp(self):
        rate = FXRate(pair="USD/EUR", rate=0.92, timestamp=None)
        d = rate.to_dict()
        assert d["timestamp"] is None

    def test_to_dict_with_sparkline(self):
        rate = FXRate(
            pair="USD/EUR", rate=0.92,
            timestamp=datetime(2026, 3, 25),
            sparkline_data=[0.91, 0.915, 0.92],
        )
        d = rate.to_dict()
        assert d["sparkline"] == [0.91, 0.915, 0.92]


class TestYieldCurveModel:
    def test_to_dict(self):
        curve = YieldCurve(
            country="US",
            timestamp=datetime(2026, 3, 25),
            tenor_10y=4.25, tenor_2y=4.10,
            spread_10y2y=15.0,
        )
        d = curve.to_dict()
        assert d["country"] == "US"
        assert d["curve"]["10Y"] == 4.25
        assert d["curve"]["2Y"] == 4.10


class TestCreditSpreadModel:
    def test_to_dict(self):
        spread = CreditSpread(
            index_name="US HY",
            spread_bps=350.5,
            timestamp=datetime(2026, 3, 25),
            percentile_90d=45.0,
        )
        d = spread.to_dict()
        assert d["index_name"] == "US HY"
        assert d["spread_bps"] == 350.5
