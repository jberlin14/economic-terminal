"""
FX Monitor Data Models

Pydantic models for FX rate data validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class FXRateData(BaseModel):
    """
    Single FX rate data point.
    
    All rates are in USD/XXX convention:
    - USD/EUR = 0.92 means 1 USD buys 0.92 EUR
    - USD/JPY = 149.50 means 1 USD buys 149.50 JPY
    """
    pair: str = Field(..., description="Currency pair (e.g., USD/EUR)")
    rate: float = Field(..., gt=0, description="Exchange rate")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default='alpha_vantage', description="Data source")
    
    # Change percentages (optional, calculated separately)
    change_1h: Optional[float] = Field(None, description="1-hour % change")
    change_24h: Optional[float] = Field(None, description="24-hour % change")
    change_1w: Optional[float] = Field(None, description="1-week % change")
    change_ytd: Optional[float] = Field(None, description="Year-to-date % change")
    
    # Sparkline data for mini chart
    sparkline: Optional[List[float]] = Field(None, description="Historical rates for mini chart")
    
    @validator('pair')
    def validate_pair(cls, v):
        """Ensure pair follows USD/XXX convention."""
        if not v.startswith('USD/') and v != 'USDX':
            raise ValueError(f"Pair must be in USD/XXX format or USDX, got {v}")
        return v
    
    @validator('rate')
    def round_rate(cls, v, values):
        """Round rate based on pair type."""
        pair = values.get('pair', '')
        if 'JPY' in pair or 'ARS' in pair:
            return round(v, 2)
        elif 'TWD' in pair:
            return round(v, 3)
        else:
            return round(v, 4)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FXUpdate(BaseModel):
    """
    Batch FX rate update containing all pairs.
    """
    rates: List[FXRateData]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default='alpha_vantage')
    success: bool = Field(default=True)
    errors: List[str] = Field(default_factory=list)
    
    @property
    def rate_dict(self) -> Dict[str, float]:
        """Get rates as a simple dictionary."""
        return {r.pair: r.rate for r in self.rates}
    
    def get_rate(self, pair: str) -> Optional[float]:
        """Get rate for a specific pair."""
        for r in self.rates:
            if r.pair == pair:
                return r.rate
        return None


class FXAlert(BaseModel):
    """
    FX risk alert data.
    """
    pair: str
    alert_type: str = Field(default='FX')
    severity: str = Field(..., description="CRITICAL, HIGH, or MEDIUM")
    change_percent: float
    change_period: str = Field(default='1h', description="Period of change (1h, 24h, etc.)")
    current_rate: float
    previous_rate: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('severity')
    def validate_severity(cls, v):
        """Ensure severity is valid."""
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v


class SparklineData(BaseModel):
    """
    Sparkline chart data for a currency pair.
    """
    pair: str
    values: List[float] = Field(..., description="Rate values for chart")
    timestamps: List[datetime] = Field(..., description="Timestamps for each value")
    min_value: float
    max_value: float
    start_time: datetime
    end_time: datetime
    interval_minutes: int = Field(default=15)
    
    @validator('values', 'timestamps')
    def check_length(cls, v, values):
        """Ensure values and timestamps have same length."""
        if 'values' in values and len(v) != len(values['values']):
            raise ValueError("values and timestamps must have same length")
        return v
    
    @property
    def normalized(self) -> List[float]:
        """Get values normalized to 0-100 range for charting."""
        if self.max_value == self.min_value:
            return [50.0] * len(self.values)
        return [
            (v - self.min_value) / (self.max_value - self.min_value) * 100
            for v in self.values
        ]


class FXSummary(BaseModel):
    """
    Summary of FX market status for dashboard/digest.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dxy_value: Optional[float] = None
    dxy_change: Optional[float] = None
    
    # Top movers
    biggest_gainer: Optional[Dict[str, Any]] = None
    biggest_loser: Optional[Dict[str, Any]] = None
    
    # All rates
    rates: Dict[str, FXRateData] = Field(default_factory=dict)
    
    # Alerts
    active_alerts: List[FXAlert] = Field(default_factory=list)
    
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
