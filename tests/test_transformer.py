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
        assert pd.isna(result.iloc[0])  # First value is NaN
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
        """YoY should be NaN when the exact prior-year date is missing."""
        dates = pd.to_datetime([
            "2024-01-01", "2024-03-01",
            "2025-01-01", "2025-02-01", "2025-03-01",
        ])
        values = [100.0, 102.0, 105.0, 106.0, 108.0]
        df = pd.DataFrame({"date": dates, "value": values})
        result = DataTransformer.calculate_yoy_change(df)
        assert result.iloc[2] == pytest.approx(5.0, abs=0.01)   # Jan 2025: Jan 2024 present
        assert pd.isna(result.iloc[3])                           # Feb 2025: Feb 2024 missing
        assert result.iloc[4] == pytest.approx(6.0, abs=0.01)   # Mar 2025: Mar 2024 present


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
        assert result["mom_change"] == pytest.approx(0.7, abs=0.01)
        assert result["yoy_change"] == pytest.approx(8.4, abs=0.01)

    def test_get_latest_with_changes_empty(self):
        t = DataTransformer()
        result = t.get_latest_with_changes(pd.DataFrame())
        assert result is None

    def test_get_latest_with_changes_none(self):
        t = DataTransformer()
        result = t.get_latest_with_changes(None)
        assert result is None
