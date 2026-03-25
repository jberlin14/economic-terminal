# Backend Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pytest-based backend test coverage for pure logic modules and API endpoints, starting from zero.

**Architecture:** Tests use an in-memory SQLite database via a shared `conftest.py` fixture. Pure logic modules (DataTransformer, credit status) are tested first with no DB dependency, then API endpoints are tested via FastAPI's `TestClient` with dependency injection overrides. Each test file mirrors the source module path.

**Tech Stack:** pytest, pytest-asyncio, httpx, FastAPI TestClient, SQLAlchemy (in-memory SQLite)

---

### Task 1: Test Infrastructure Setup

**Files:**
- Modify: `requirements.txt` (add test dependencies)
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Append to `requirements.txt`:
```
# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
pytest-cov>=5.0.0
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts = -v --tb=short
```

- [ ] **Step 3: Create tests/__init__.py**

Empty file.

- [ ] **Step 4: Create tests/conftest.py with DB fixtures**

```python
"""Shared test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from modules.data_storage.schema import Base
from modules.data_storage.database import get_db
from backend.main import app


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a DB session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with DB override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Install dependencies and verify pytest runs**

Run: `pip install pytest pytest-asyncio httpx pytest-cov`
Run: `pytest --co`
Expected: "no tests ran" (collected 0 items)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/
git commit -m "feat: add pytest infrastructure with in-memory DB fixtures"
```

---

### Task 2: DataTransformer Unit Tests

**Files:**
- Create: `tests/test_transformer.py`

This is the highest-value test target: pure logic, no DB, no mocks needed.

- [ ] **Step 1: Write tests for basic calculations**

```python
"""Tests for DataTransformer — pure logic, no DB."""

import pandas as pd
import numpy as np
import pytest
from modules.economic_indicators.transformer import DataTransformer


@pytest.fixture
def monthly_data():
    """12 months of CPI-like data."""
    dates = pd.date_range("2025-01-01", periods=12, freq="MS")
    values = [300.0, 300.5, 301.2, 301.8, 302.5, 303.0,
              303.8, 304.2, 304.9, 305.5, 306.0, 306.8]
    return pd.DataFrame({"date": dates, "value": values})


@pytest.fixture
def two_year_data():
    """24 months for YoY testing."""
    dates = pd.date_range("2024-01-01", periods=24, freq="MS")
    values = [290 + i * 0.7 for i in range(24)]
    return pd.DataFrame({"date": dates, "value": values})


class TestBasicCalculations:
    def test_calculate_change(self, monthly_data):
        result = DataTransformer.calculate_change(monthly_data)
        assert result.iloc[0] != result.iloc[0]  # First value is NaN
        assert result.iloc[1] == pytest.approx(0.5, abs=0.01)

    def test_calculate_percent_change(self, monthly_data):
        result = DataTransformer.calculate_percent_change(monthly_data)
        expected = (0.5 / 300.0) * 100
        assert result.iloc[1] == pytest.approx(expected, abs=0.01)

    def test_moving_average_3(self, monthly_data):
        result = DataTransformer.calculate_moving_average(monthly_data, periods=3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        expected = (300.0 + 300.5 + 301.2) / 3
        assert result.iloc[2] == pytest.approx(expected, abs=0.01)

    def test_empty_dataframe(self):
        df = pd.DataFrame({"date": [], "value": []})
        result = DataTransformer.calculate_change(df)
        assert len(result) == 0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_transformer.py::TestBasicCalculations -v`
Expected: 4 PASSED

- [ ] **Step 3: Write tests for date-based YoY/MoM**

Add to `tests/test_transformer.py`:

```python
class TestDateBasedCalculations:
    def test_mom_change(self, monthly_data):
        result = DataTransformer.calculate_mom_change(monthly_data)
        # Jan has no prior month, should be NaN
        assert pd.isna(result.iloc[0])
        # Feb - Jan = 300.5 - 300.0
        assert result.iloc[1] == pytest.approx(0.5, abs=0.01)

    def test_mom_percent(self, monthly_data):
        result = DataTransformer.calculate_mom_percent(monthly_data)
        expected = (0.5 / 300.0) * 100
        assert result.iloc[1] == pytest.approx(expected, abs=0.01)

    def test_yoy_change_with_full_year(self, two_year_data):
        result = DataTransformer.calculate_yoy_change(two_year_data)
        # First 12 months have no year-ago data
        for i in range(12):
            assert pd.isna(result.iloc[i])
        # Month 13 (Jan 2025) vs Month 1 (Jan 2024)
        expected = two_year_data["value"].iloc[12] - two_year_data["value"].iloc[0]
        assert result.iloc[12] == pytest.approx(expected, abs=0.01)

    def test_yoy_handles_data_gap(self):
        """YoY should return NaN when prior-year date is missing."""
        dates = pd.to_datetime(["2024-01-01", "2024-03-01", "2025-01-01", "2025-03-01"])
        values = [100.0, 102.0, 105.0, 108.0]
        df = pd.DataFrame({"date": dates, "value": values})
        result = DataTransformer.calculate_yoy_change(df)
        # Jan 2025 has Jan 2024 match
        assert result.iloc[2] == pytest.approx(5.0, abs=0.01)
        # Mar 2025 has Mar 2024 match
        assert result.iloc[3] == pytest.approx(6.0, abs=0.01)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_transformer.py::TestDateBasedCalculations -v`
Expected: 4 PASSED

- [ ] **Step 5: Write tests for transform() and get_latest_with_changes()**

Add to `tests/test_transformer.py`:

```python
class TestTransformMethod:
    def test_transform_adds_columns(self, monthly_data):
        t = DataTransformer()
        result = t.transform(monthly_data, ["mom_change", "ma_3"])
        assert "mom_change" in result.columns
        assert "ma_3" in result.columns
        assert "value" in result.columns

    def test_transform_dynamic_ma(self, monthly_data):
        t = DataTransformer()
        result = t.transform(monthly_data, ["ma_6"])
        assert "ma_6" in result.columns

    def test_get_latest_with_changes_returns_dict(self, two_year_data):
        t = DataTransformer()
        result = t.get_latest_with_changes(two_year_data)
        assert result is not None
        assert "date" in result
        assert "value" in result
        assert "mom_change" in result
        assert "yoy_change" in result
        assert isinstance(result["value"], float)

    def test_get_latest_with_changes_empty(self):
        t = DataTransformer()
        result = t.get_latest_with_changes(pd.DataFrame())
        assert result is None

    def test_get_latest_with_changes_none(self):
        t = DataTransformer()
        result = t.get_latest_with_changes(None)
        assert result is None
```

- [ ] **Step 6: Run all transformer tests**

Run: `pytest tests/test_transformer.py -v`
Expected: 13 PASSED

- [ ] **Step 7: Commit**

```bash
git add tests/test_transformer.py
git commit -m "test: add DataTransformer unit tests (13 cases)"
```

---

### Task 3: Credit Status Utility Tests

**Files:**
- Create: `tests/test_credit.py`

Tests the pure `_assess_credit_status()` function and credit API endpoints.

- [ ] **Step 1: Write tests for _assess_credit_status**

```python
"""Tests for credit API — pure logic and endpoints."""

import pytest
from unittest.mock import MagicMock
from backend.api.credit import _assess_credit_status


class TestAssessCreditStatus:
    def _make_spread(self, percentile):
        spread = MagicMock()
        spread.percentile_90d = percentile
        return spread

    def test_normal_status(self):
        spreads = [self._make_spread(50), self._make_spread(70)]
        assert _assess_credit_status(spreads) == "NORMAL"

    def test_elevated_at_90(self):
        spreads = [self._make_spread(50), self._make_spread(90)]
        assert _assess_credit_status(spreads) == "ELEVATED"

    def test_stressed_at_95(self):
        spreads = [self._make_spread(95), self._make_spread(50)]
        assert _assess_credit_status(spreads) == "STRESSED"

    def test_stressed_beats_elevated(self):
        """First match wins — stressed at 95 found before elevated at 90."""
        spreads = [self._make_spread(95), self._make_spread(90)]
        assert _assess_credit_status(spreads) == "STRESSED"

    def test_none_percentile_treated_as_normal(self):
        spreads = [self._make_spread(None), self._make_spread(None)]
        assert _assess_credit_status(spreads) == "NORMAL"

    def test_empty_spreads(self):
        assert _assess_credit_status([]) == "NORMAL"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_credit.py -v`
Expected: 6 PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_credit.py
git commit -m "test: add credit status assessment tests (6 cases)"
```

---

### Task 4: Health API Endpoint Tests

**Files:**
- Create: `tests/test_api_health.py`

- [ ] **Step 1: Write health endpoint tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_api_health.py -v`
Expected: 5 PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_health.py
git commit -m "test: add health API endpoint tests (5 cases)"
```

---

### Task 5: Credit & FX API Endpoint Tests

**Files:**
- Create: `tests/test_api_credit.py`
- Create: `tests/test_api_fx.py`

- [ ] **Step 1: Write credit API endpoint tests**

```python
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
```

- [ ] **Step 2: Write FX API endpoint tests**

```python
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
```

- [ ] **Step 3: Run all new API tests**

Run: `pytest tests/test_api_credit.py tests/test_api_fx.py -v`
Expected: 12 PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/test_api_credit.py tests/test_api_fx.py
git commit -m "test: add credit and FX API endpoint tests (12 cases)"
```

---

### Task 6: Yields API Endpoint Tests

**Files:**
- Create: `tests/test_api_yields.py`

- [ ] **Step 1: Write yields endpoint tests**

```python
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
        response = client.get("/api/yields/curve")
        assert response.status_code == 200

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
        response = client.get("/api/yields/history?days=0")
        assert response.status_code == 422
        response = client.get("/api/yields/history?days=366")
        assert response.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_api_yields.py -v`
Expected: 7 PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_yields.py
git commit -m "test: add yields API endpoint tests (7 cases)"
```

---

### Task 7: Schema Model Tests

**Files:**
- Create: `tests/test_schema.py`

- [ ] **Step 1: Write model serialization tests**

```python
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
        rate = FXRate(pair="USD/EUR", rate=0.92)
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_schema.py -v`
Expected: 5 PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_schema.py
git commit -m "test: add schema model serialization tests (5 cases)"
```

---

### Task 8: Run Full Suite with Coverage

- [ ] **Step 1: Run all tests with coverage**

Run: `pytest --cov=backend --cov=modules --cov-report=term-missing -v`
Expected: 48 tests PASSED, coverage report printed

- [ ] **Step 2: Verify no import errors or warnings**

Check output for any warnings about missing modules or import failures.

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git commit -m "test: fix any test issues from full suite run"
```
