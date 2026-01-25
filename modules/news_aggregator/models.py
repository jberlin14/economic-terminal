"""
News Aggregator Data Models

Pydantic models for news article data validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import hashlib


class NewsArticle(BaseModel):
    """
    Single news article.
    """
    headline: str = Field(..., description="Article headline")
    source: str = Field(..., description="Source (bloomberg, cnbc, yahoo)")
    url: str = Field(..., description="Article URL")
    published_at: datetime = Field(..., description="Publication timestamp")

    # Categorization
    country_tags: List[str] = Field(default_factory=list, description="Country tags (US, JP, etc)")
    category: str = Field(default='GENERAL', description="Category (ECON, FX, POLITICAL, etc)")
    severity: str = Field(default='LOW', description="Severity (CRITICAL, HIGH, MEDIUM, LOW)")

    # Optional content
    summary: Optional[str] = Field(None, description="Article summary")
    full_text: Optional[str] = Field(None, description="Full article text")

    # Metadata
    content_hash: Optional[str] = Field(None, description="Hash for deduplication")
    relevance_score: Optional[float] = Field(None, description="Relevance score")
    keyword_matches: List[str] = Field(default_factory=list, description="Matched keywords")

    @validator('severity')
    def validate_severity(cls, v):
        """Ensure severity is valid."""
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v

    @validator('content_hash', pre=True, always=True)
    def generate_hash(cls, v, values):
        """Generate content hash if not provided."""
        if v is None and 'headline' in values and 'url' in values:
            content = f"{values['headline']}:{values['url']}"
            return hashlib.sha256(content.encode()).hexdigest()
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NewsFeed(BaseModel):
    """
    Batch news feed update containing multiple articles.
    """
    articles: List[NewsArticle]
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = Field(default=True)
    errors: List[str] = Field(default_factory=list)

    @property
    def article_count(self) -> int:
        """Get total article count."""
        return len(self.articles)

    @property
    def critical_count(self) -> int:
        """Count critical articles."""
        return sum(1 for a in self.articles if a.severity == 'CRITICAL')

    @property
    def high_count(self) -> int:
        """Count high severity articles."""
        return sum(1 for a in self.articles if a.severity == 'HIGH')

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NewsAlert(BaseModel):
    """
    News-based alert data.
    """
    headline: str
    source: str
    url: str
    alert_type: str = Field(default='NEWS')
    severity: str = Field(..., description="CRITICAL, HIGH, or MEDIUM")
    message: str
    country_tags: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator('severity')
    def validate_severity(cls, v):
        """Ensure severity is valid."""
        valid = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if v not in valid:
            raise ValueError(f"Severity must be one of {valid}")
        return v


class NewsSummary(BaseModel):
    """
    Summary of recent news for dashboard.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    total_articles: int = 0
    critical_articles: List[NewsArticle] = Field(default_factory=list)
    high_articles: List[NewsArticle] = Field(default_factory=list)
    recent_articles: List[NewsArticle] = Field(default_factory=list)

    # By country
    by_country: Dict[str, int] = Field(default_factory=dict)

    # By source
    by_source: Dict[str, int] = Field(default_factory=dict)

    @property
    def has_critical(self) -> bool:
        """Check if there are any critical articles."""
        return len(self.critical_articles) > 0