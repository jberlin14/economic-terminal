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
