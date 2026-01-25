"""
Credit Monitor Data Models

Pydantic models for credit spread data validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class CreditSpreadData(BaseModel):
    """
    Single credit spread data point.

    Represents Option-Adjusted Spread (OAS) for credit indices.
    """
    index_name: str = Field(..., description="Index name (e.g., US_IG, US_HY)")
    spread_bps: float = Field(..., gt=0, description="Spread in basis points")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default='fred', description="Data source")
    fred_series: Optional[str] = Field(None, description="FRED series ID")

    # Calculated metrics
    percentile_90d: Optional[float] = Field(None, description="90-day percentile rank")
    percentile_1y: Optional[float] = Field(None, description="1-year percentile rank")
    avg_30d: Optional[float] = Field(None, description="30-day average")
    avg_90d: Optional[float] = Field(None, description="90-day average")
    change_1d: Optional[float] = Field(None, description="1-day change in bps")
    change_1w: Optional[float] = Field(None, description="1-week change in bps")

    @validator('spread_bps')
    def round_spread(cls, v):
        """Round spread to 2 decimal places."""
        return round(v, 2)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CreditUpdate(BaseModel):
    """
    Batch credit spread update containing all indices.
    """
    spreads: List[CreditSpreadData]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default='fred')
    success: bool = Field(default=True)
    errors: List[str] = Field(default_factory=list)

    @property
    def spread_dict(self) -> Dict[str, float]:
        """Get spreads as a simple dictionary."""
        return {s.index_name: s.spread_bps for s in self.spreads}

    def get_spread(self, index_name: str) -> Optional[float]:
        """Get spread for a specific index."""
        for s in self.spreads:
            if s.index_name == index_name:
                return s.spread_bps
        return None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CreditAlert(BaseModel):
    """
    Credit spread risk alert data.
    """
    index_name: str
    alert_type: str = Field(default='CREDIT')
    severity: str = Field(..., description="CRITICAL, HIGH, or MEDIUM")
    spread_bps: float
    percentile: Optional[float] = None
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator('severity')
    def validate_severity(cls, v):
        """Ensure severity is valid."""
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v


class CreditSummary(BaseModel):
    """
    Summary of credit market status for dashboard/digest.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Current spreads
    us_ig: Optional[float] = None
    us_bbb: Optional[float] = None
    us_hy: Optional[float] = None
    us_hy_ccc: Optional[float] = None

    # Percentile ranks
    us_ig_pct: Optional[float] = None
    us_bbb_pct: Optional[float] = None
    us_hy_pct: Optional[float] = None
    us_hy_ccc_pct: Optional[float] = None

    # All spread data
    spreads: Dict[str, CreditSpreadData] = Field(default_factory=dict)

    # Alerts
    active_alerts: List[CreditAlert] = Field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        """Check if there are any critical alerts."""
        return any(a.severity == 'CRITICAL' for a in self.active_alerts)

    @property
    def alert_count(self) -> Dict[str, int]:
        """Count alerts by severity."""
        counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0}
        for alert in self.active_alerts:
            counts[alert.severity] = counts.get(alert.severity, 0) + 1
        return counts