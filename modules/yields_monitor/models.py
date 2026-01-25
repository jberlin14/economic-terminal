"""
Yields Monitor Data Models

Pydantic models for yield curve data.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator


class YieldPoint(BaseModel):
    """Single point on the yield curve."""
    tenor: str = Field(..., description="Tenor label (e.g., '10Y')")
    yield_value: float = Field(..., description="Yield in percentage (e.g., 4.25)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('yield_value')
    def round_yield(cls, v):
        return round(v, 2)


class YieldSpread(BaseModel):
    """Yield spread between two tenors."""
    name: str = Field(..., description="Spread name (e.g., '10Y-2Y')")
    value: float = Field(..., description="Spread in percentage points")
    value_bps: float = Field(..., description="Spread in basis points")
    long_tenor: str
    short_tenor: str
    long_yield: float
    short_yield: float
    is_inverted: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('value_bps', pre=True, always=True)
    def calculate_bps(cls, v, values):
        if v is None and 'value' in values:
            return values['value'] * 100
        return v
    
    @validator('is_inverted', pre=True, always=True)
    def check_inversion(cls, v, values):
        if 'value' in values:
            return values['value'] < 0
        return v


class YieldCurveData(BaseModel):
    """Complete yield curve snapshot."""
    country: str = Field(default='US')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default='fred')
    
    # Individual tenors
    tenor_1m: Optional[float] = None
    tenor_3m: Optional[float] = None
    tenor_6m: Optional[float] = None
    tenor_1y: Optional[float] = None
    tenor_2y: Optional[float] = None
    tenor_5y: Optional[float] = None
    tenor_10y: Optional[float] = None
    tenor_20y: Optional[float] = None
    tenor_30y: Optional[float] = None
    
    # TIPS (real yields)
    tips_5y: Optional[float] = None
    tips_10y: Optional[float] = None
    
    # Calculated spreads
    spread_10y2y: Optional[float] = None
    spread_10y3m: Optional[float] = None
    spread_30y10y: Optional[float] = None
    
    @property
    def curve_dict(self) -> Dict[str, Optional[float]]:
        """Get curve as dictionary."""
        return {
            '1M': self.tenor_1m,
            '3M': self.tenor_3m,
            '6M': self.tenor_6m,
            '1Y': self.tenor_1y,
            '2Y': self.tenor_2y,
            '5Y': self.tenor_5y,
            '10Y': self.tenor_10y,
            '20Y': self.tenor_20y,
            '30Y': self.tenor_30y,
        }
    
    @property
    def curve_list(self) -> List[Dict[str, Any]]:
        """Get curve as list of points for charting."""
        curve = self.curve_dict
        return [
            {'tenor': k, 'yield': v}
            for k, v in curve.items()
            if v is not None
        ]
    
    @property
    def is_inverted(self) -> bool:
        """Check if curve is inverted (10Y-2Y < 0)."""
        return self.spread_10y2y is not None and self.spread_10y2y < 0
    
    @property
    def inversion_depth(self) -> Optional[float]:
        """Get depth of inversion in basis points."""
        if self.spread_10y2y is None:
            return None
        if self.spread_10y2y >= 0:
            return 0
        return abs(self.spread_10y2y * 100)
    
    def calculate_spreads(self) -> None:
        """Calculate all spreads from tenor values."""
        if self.tenor_10y is not None and self.tenor_2y is not None:
            self.spread_10y2y = round(self.tenor_10y - self.tenor_2y, 4)
        
        if self.tenor_10y is not None and self.tenor_3m is not None:
            self.spread_10y3m = round(self.tenor_10y - self.tenor_3m, 4)
        
        if self.tenor_30y is not None and self.tenor_10y is not None:
            self.spread_30y10y = round(self.tenor_30y - self.tenor_10y, 4)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class YieldCurveChange(BaseModel):
    """Change in yield curve between two points in time."""
    current: YieldCurveData
    previous: YieldCurveData
    time_delta_hours: float
    
    # Calculated changes (in basis points)
    change_10y: Optional[float] = None
    change_2y: Optional[float] = None
    change_spread: Optional[float] = None
    
    @property
    def tenor_changes(self) -> Dict[str, Optional[float]]:
        """Get changes for each tenor in basis points."""
        changes = {}
        for tenor in ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']:
            attr = f"tenor_{tenor.lower().replace('-', '')}"
            current_val = getattr(self.current, attr, None)
            prev_val = getattr(self.previous, attr, None)
            
            if current_val is not None and prev_val is not None:
                changes[tenor] = round((current_val - prev_val) * 100, 1)  # bps
            else:
                changes[tenor] = None
        
        return changes
    
    @property
    def is_steepening(self) -> bool:
        """Check if curve is steepening (long rates rising faster than short)."""
        if self.change_spread is None:
            return False
        return self.change_spread > 0
    
    @property
    def is_flattening(self) -> bool:
        """Check if curve is flattening."""
        if self.change_spread is None:
            return False
        return self.change_spread < 0


class YieldAlert(BaseModel):
    """Yield-related risk alert."""
    alert_type: str = Field(default='YIELDS')
    severity: str
    category: str = Field(..., description="INVERSION, STEEPENING, LEVEL")
    message: str
    spread_name: Optional[str] = None
    spread_value: Optional[float] = None
    threshold_breached: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('severity')
    def validate_severity(cls, v):
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v


class YieldSummary(BaseModel):
    """Summary of yield curve status for dashboard."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Current curve
    current_curve: Optional[YieldCurveData] = None
    
    # Key metrics
    yield_10y: Optional[float] = None
    yield_2y: Optional[float] = None
    spread_10y2y: Optional[float] = None
    spread_10y2y_bps: Optional[float] = None
    
    # Status
    is_inverted: bool = False
    inversion_depth_bps: Optional[float] = None
    
    # 1-week ago curve for comparison
    historical_curve: Optional[YieldCurveData] = None
    
    # Active alerts
    alerts: List[YieldAlert] = Field(default_factory=list)
    
    @property
    def has_critical(self) -> bool:
        return any(a.severity == 'CRITICAL' for a in self.alerts)
