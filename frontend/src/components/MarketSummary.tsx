import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Brain, ChevronDown, ChevronUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface KeyMetric {
  name: string;
  value: string;
  trend: 'up' | 'down' | 'neutral' | 'warning';
  importance: 'high' | 'medium' | 'low';
}

interface MarketSummaryData {
  timestamp: string;
  headline: string;
  overview: string;
  sections: {
    inflation: string;
    labor: string;
    growth: string;
    rates: string;
  };
  key_metrics: KeyMetric[];
  sentiment: 'very_bullish' | 'bullish' | 'neutral' | 'bearish' | 'very_bearish';
  alerts: string[];
  trends: {
    inflation?: string;
    employment?: string;
    growth?: string;
  };
}

export const MarketSummary: React.FC = () => {
  const [summary, setSummary] = useState<MarketSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<string[]>(['overview']);

  useEffect(() => {
    fetchSummary();
    // Refresh every 5 minutes
    const interval = setInterval(fetchSummary, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchSummary = async () => {
    try {
      const response = await fetch(`${API_URL}/api/summary`);
      if (!response.ok) throw new Error('Failed to fetch summary');
      const data = await response.json();
      setSummary(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load summary');
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section) ? prev.filter(s => s !== section) : [...prev, section]
    );
  };

  const getSentimentColor = (sentiment: string) => {
    const colors: Record<string, string> = {
      very_bullish: 'text-positive bg-positive/20',
      bullish: 'text-positive bg-positive/10',
      neutral: 'text-terminal-text-dim bg-terminal-dark',
      bearish: 'text-warning bg-warning/10',
      very_bearish: 'text-critical bg-critical/20'
    };
    return colors[sentiment] || colors.neutral;
  };

  const getSentimentLabel = (sentiment: string) => {
    const labels: Record<string, string> = {
      very_bullish: 'Very Bullish',
      bullish: 'Bullish',
      neutral: 'Neutral',
      bearish: 'Bearish',
      very_bearish: 'Very Bearish'
    };
    return labels[sentiment] || 'Neutral';
  };

  const getTrendIcon = (trend: string) => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4 text-positive" />;
    if (trend === 'down') return <TrendingDown className="w-4 h-4 text-critical" />;
    if (trend === 'warning') return <AlertTriangle className="w-4 h-4 text-warning" />;
    return <Minus className="w-4 h-4 text-terminal-text-dim" />;
  };

  if (loading) {
    return (
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-terminal-dark rounded w-3/4"></div>
          <div className="h-4 bg-terminal-dark rounded w-full"></div>
          <div className="h-4 bg-terminal-dark rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-6">
        <div className="text-terminal-text-dim text-center">
          <Brain className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>Unable to generate market summary</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-terminal-panel border border-terminal-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-neutral/20 to-transparent p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-6 h-6 text-neutral" />
            <div>
              <h2 className="font-bold text-lg">Market Intelligence</h2>
              <p className="text-xs text-terminal-text-dim">AI-Generated Analysis</p>
            </div>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${getSentimentColor(summary.sentiment)}`}>
            {getSentimentLabel(summary.sentiment)}
          </div>
        </div>
      </div>

      {/* Headline */}
      <div className="p-4 border-b border-terminal-border">
        <h3 className="text-xl font-bold text-terminal-text">{summary.headline}</h3>
      </div>

      {/* Alerts */}
      {summary.alerts && summary.alerts.length > 0 && (
        <div className="p-4 bg-warning/10 border-b border-warning/30">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              {summary.alerts.map((alert, idx) => (
                <p key={idx} className="text-sm text-warning">{alert}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Key Metrics */}
      <div className="p-4 border-b border-terminal-border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {summary.key_metrics.slice(0, 4).map((metric, idx) => (
            <div key={idx} className="bg-terminal-dark rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-terminal-text-dim">{metric.name}</span>
                {getTrendIcon(metric.trend)}
              </div>
              <div className="text-lg font-bold font-mono">{metric.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Overview Section */}
      <div className="border-b border-terminal-border">
        <button
          onClick={() => toggleSection('overview')}
          className="w-full p-4 flex items-center justify-between hover:bg-terminal-dark/50 transition-colors"
        >
          <span className="font-medium">Overview</span>
          {expandedSections.includes('overview') ? (
            <ChevronUp className="w-5 h-5 text-terminal-text-dim" />
          ) : (
            <ChevronDown className="w-5 h-5 text-terminal-text-dim" />
          )}
        </button>
        {expandedSections.includes('overview') && (
          <div className="px-4 pb-4">
            <p className="text-terminal-text leading-relaxed">{summary.overview}</p>
          </div>
        )}
      </div>

      {/* Detailed Sections */}
      {Object.entries(summary.sections).map(([key, content]) => (
        <div key={key} className="border-b border-terminal-border last:border-b-0">
          <button
            onClick={() => toggleSection(key)}
            className="w-full p-4 flex items-center justify-between hover:bg-terminal-dark/50 transition-colors"
          >
            <span className="font-medium capitalize">{key}</span>
            <div className="flex items-center gap-2">
              {summary.trends[key as keyof typeof summary.trends] && (
                <span className={`text-xs px-2 py-0.5 rounded ${
                  summary.trends[key as keyof typeof summary.trends] === 'improving'
                    ? 'bg-positive/20 text-positive'
                    : summary.trends[key as keyof typeof summary.trends] === 'deteriorating'
                    ? 'bg-critical/20 text-critical'
                    : 'bg-terminal-dark text-terminal-text-dim'
                }`}>
                  {summary.trends[key as keyof typeof summary.trends]}
                </span>
              )}
              {expandedSections.includes(key) ? (
                <ChevronUp className="w-5 h-5 text-terminal-text-dim" />
              ) : (
                <ChevronDown className="w-5 h-5 text-terminal-text-dim" />
              )}
            </div>
          </button>
          {expandedSections.includes(key) && (
            <div className="px-4 pb-4">
              <p className="text-terminal-text-dim leading-relaxed">{content}</p>
            </div>
          )}
        </div>
      ))}

      {/* Footer */}
      <div className="p-3 bg-terminal-dark/50 text-xs text-terminal-text-dim text-center">
        Generated {new Date(summary.timestamp).toLocaleString('en-US', { timeZone: 'America/New_York' })} ET
      </div>
    </div>
  );
};
