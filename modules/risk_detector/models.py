"""
Risk Detector Data Models
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator
import hashlib


class RiskAlertData(BaseModel):
    """Risk alert data model."""
    alert_type: str = Field(..., description="FX, YIELDS, CREDIT, POLITICAL, ECON, CAT")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM")
    title: str
    message: str
    
    # Related data
    related_entity: Optional[str] = None  # e.g., 'USD/JPY', 'HY_OAS'
    related_value: Optional[float] = None
    threshold_value: Optional[float] = None
    
    # Metadata
    country: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    
    # Timestamps
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Additional details
    details: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('severity')
    def validate_severity(cls, v):
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v
    
    @validator('alert_type')
    def validate_type(cls, v):
        valid = ['FX', 'YIELDS', 'CREDIT', 'POLITICAL', 'ECON', 'CAT']
        if v not in valid:
            raise ValueError(f"Alert type must be one of {valid}")
        return v
    
    @property
    def alert_hash(self) -> str:
        """Generate a hash for deduplication."""
        content = f"{self.alert_type}:{self.related_entity}:{self.severity}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_type': self.alert_type,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'related_entity': self.related_entity,
            'related_value': self.related_value,
            'triggered_at': self.triggered_at.isoformat(),
            'country': self.country,
            'details': self.details
        }


class AlertBatch(BaseModel):
    """Batch of alerts for processing."""
    alerts: List[RiskAlertData] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_module: str = 'unknown'
    
    @property
    def critical_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == 'CRITICAL')
    
    @property
    def high_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == 'HIGH')
    
    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0


class AlertSummary(BaseModel):
    """Summary of active alerts."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    total_active: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    
    critical_alerts: List[RiskAlertData] = Field(default_factory=list)
    high_alerts: List[RiskAlertData] = Field(default_factory=list)
    
    @property
    def has_critical(self) -> bool:
        return len(self.critical_alerts) > 0
