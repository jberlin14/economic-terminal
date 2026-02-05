import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, AlertCircle, Clock, ChevronDown } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface DataQuality {
  quality_score: number;
  quality_level: string;
  indicators_available: number;
  indicators_expected: number;
  missing_critical: string[];
  missing_important: string[];
  yield_curve_available: boolean;
  fx_data_available: boolean;
  credit_data_available: boolean;
  news_count: number;
  news_health: string;
}

interface NarrativeData {
  narrative: string;
  generated_at: string;
  model: string;
  narrative_type?: string;
  narrative_mode?: string;
  tokens_used: number;
  indicators_count: number;
  news_count: number;
  context_snapshot?: string;
  market_regime?: string;
  from_cache?: boolean;
  cache_age_minutes?: number;
  data_quality?: DataQuality;
  is_fallback?: boolean;
}

interface NarrativeMode {
  name: string;
  description: string;
  icon: string;
}

export const MarketNarrative: React.FC = () => {
  const [narrative, setNarrative] = useState<NarrativeData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [modes, setModes] = useState<Record<string, NarrativeMode>>({});
  const [selectedMode, setSelectedMode] = useState<string>('comprehensive');
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [showContextSnapshot, setShowContextSnapshot] = useState(false);
  const [showDataQuality, setShowDataQuality] = useState(false);

  // Check if AI is available and fetch modes on mount
  useEffect(() => {
    checkAvailability();
    fetchModes();
  }, []);

  const checkAvailability = async () => {
    try {
      const response = await fetch(`${API_URL}/api/narrative/status`);
      const data = await response.json();
      setAvailable(data.available);
    } catch {
      setAvailable(false);
    }
  };

  const fetchModes = async () => {
    try {
      const response = await fetch(`${API_URL}/api/narrative/modes`);
      const data = await response.json();
      setModes(data);
    } catch (err) {
      console.error('Failed to fetch narrative modes:', err);
    }
  };

  const generateNarrative = async () => {
    setLoading(true);
    setError(null);
    setShowModeSelector(false);

    try {
      const response = await fetch(`${API_URL}/api/narrative/generate?narrative_type=${selectedMode}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate narrative');
      }

      const data = await response.json();
      setNarrative(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate narrative');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZone: 'America/New_York'
    }) + ' ET';
  };

  // Render paragraphs from the narrative text
  const renderNarrative = (text: string) => {
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    return paragraphs.map((paragraph, idx) => (
      <p key={idx} className="mb-4 last:mb-0 leading-relaxed">
        {paragraph}
      </p>
    ));
  };

  return (
    <div className="bg-terminal-panel border border-terminal-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-900/30 to-transparent p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Brain className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="font-bold text-lg">Market Intelligence</h2>
              <p className="text-xs text-terminal-text-dim">AI-Powered Analysis</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Mode Selector */}
            {Object.keys(modes).length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setShowModeSelector(!showModeSelector)}
                  className="flex items-center gap-2 px-3 py-2 bg-terminal-dark border border-terminal-border rounded-lg hover:border-purple-500/50 transition-colors"
                >
                  <span className="text-sm">
                    {modes[selectedMode]?.icon} {modes[selectedMode]?.name || 'Select Mode'}
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${showModeSelector ? 'rotate-180' : ''}`} />
                </button>

                {showModeSelector && (
                  <div className="absolute right-0 mt-2 w-80 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                    {Object.entries(modes).map(([key, mode]) => (
                      <button
                        key={key}
                        onClick={() => {
                          setSelectedMode(key);
                          setShowModeSelector(false);
                        }}
                        className={`w-full text-left px-4 py-3 hover:bg-purple-500/10 transition-colors border-b border-terminal-border last:border-b-0 ${
                          selectedMode === key ? 'bg-purple-500/20' : ''
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <span className="text-lg">{mode.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm">{mode.name}</div>
                            <div className="text-xs text-terminal-text-dim mt-1">{mode.description}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Generate Button */}
            <button
              onClick={generateNarrative}
              disabled={loading || available === false}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                loading
                  ? 'bg-purple-900/50 text-purple-300 cursor-wait'
                  : available === false
                  ? 'bg-terminal-dark text-terminal-text-dim cursor-not-allowed'
                  : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-500/20'
              }`}
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Analysis</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {/* Not Available State */}
        {available === false && (
          <div className="flex items-center gap-3 p-4 bg-warning/10 border border-warning/30 rounded-lg">
            <AlertCircle className="w-5 h-5 text-warning flex-shrink-0" />
            <div>
              <p className="text-warning font-medium">AI Generation Unavailable</p>
              <p className="text-sm text-terminal-text-dim mt-1">
                Please configure ANTHROPIC_API_KEY in your .env file to enable AI-powered analysis.
              </p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-critical/10 border border-critical/30 rounded-lg mb-4">
            <AlertCircle className="w-5 h-5 text-critical flex-shrink-0" />
            <div>
              <p className="text-critical font-medium">Generation Failed</p>
              <p className="text-sm text-terminal-text-dim mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-purple-400">
              <div className="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
              <span>Analyzing market data and generating narrative...</span>
            </div>
            <div className="space-y-3">
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-full" />
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-11/12" />
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-full" />
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-10/12" />
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-full" />
              <div className="h-4 bg-terminal-dark rounded animate-pulse w-9/12" />
            </div>
          </div>
        )}

        {/* Empty State */}
        {!loading && !narrative && available !== false && (
          <div className="text-center py-8">
            <Brain className="w-16 h-16 text-terminal-text-dim mx-auto mb-4 opacity-30" />
            <p className="text-terminal-text-dim text-lg mb-2">No analysis generated yet</p>
            <p className="text-terminal-text-dim text-sm">
              Click "Generate Analysis" to create an AI-powered market narrative
              <br />
              based on current economic data, news, and market conditions.
            </p>
          </div>
        )}

        {/* Narrative Content */}
        {!loading && narrative && (
          <div>
            <div className="prose prose-invert max-w-none text-terminal-text">
              {renderNarrative(narrative.narrative)}
            </div>

            {/* Footer with metadata */}
            <div className="mt-6 pt-4 border-t border-terminal-border flex items-center justify-between text-xs text-terminal-text-dim flex-wrap gap-3">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTimestamp(narrative.generated_at)}
                </span>
                {narrative.narrative_mode && (
                  <>
                    <span>|</span>
                    <span className="flex items-center gap-1">
                      <span>{modes[narrative.narrative_type || '']?.icon || '📊'}</span>
                      <span>{narrative.narrative_mode}</span>
                    </span>
                  </>
                )}
                {narrative.market_regime && (
                  <>
                    <span>|</span>
                    <span>Regime: {narrative.market_regime}</span>
                  </>
                )}
                <span>|</span>
                <span>{narrative.indicators_count} indicators</span>
                <span>|</span>
                <span>{narrative.news_count} news items</span>
                {narrative.data_quality && (
                  <>
                    <span>|</span>
                    <span className={`px-2 py-0.5 rounded ${
                      narrative.data_quality.quality_level === 'EXCELLENT' ? 'bg-green-500/20 text-green-400' :
                      narrative.data_quality.quality_level === 'GOOD' ? 'bg-blue-500/20 text-blue-400' :
                      narrative.data_quality.quality_level === 'FAIR' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      Data: {narrative.data_quality.quality_score}/100
                    </span>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2">
                {narrative.is_fallback ? (
                  <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                    Template Mode
                  </span>
                ) : (
                  <>
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                      Claude Sonnet 4.5
                    </span>
                    {narrative.from_cache && (
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                        Cached ({narrative.cache_age_minutes}m)
                      </span>
                    )}
                    <span>{narrative.tokens_used.toLocaleString()} tokens</span>
                  </>
                )}
              </div>
            </div>

            {/* Data Quality Details */}
            {narrative.data_quality && (
              <div className="mt-4 pt-4 border-t border-terminal-border">
                <button
                  onClick={() => setShowDataQuality(!showDataQuality)}
                  className="flex items-center gap-2 text-xs text-terminal-text-dim hover:text-terminal-text transition-colors"
                >
                  <ChevronDown className={`w-3 h-3 transition-transform ${showDataQuality ? 'rotate-180' : ''}`} />
                  <span>View Data Quality Details</span>
                </button>
                {showDataQuality && (
                  <div className="mt-3 p-4 bg-terminal-dark rounded-lg border border-terminal-border">
                    <div className="text-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-terminal-text-dim">Overall Quality:</span>
                        <span className={`font-bold ${
                          narrative.data_quality.quality_level === 'EXCELLENT' ? 'text-green-400' :
                          narrative.data_quality.quality_level === 'GOOD' ? 'text-blue-400' :
                          narrative.data_quality.quality_level === 'FAIR' ? 'text-yellow-400' :
                          'text-red-400'
                        }`}>
                          {narrative.data_quality.quality_level} ({narrative.data_quality.quality_score}/100)
                        </span>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-terminal-text-dim">Indicators:</span>
                        <span>{narrative.data_quality.indicators_available} / {narrative.data_quality.indicators_expected}</span>
                      </div>

                      {narrative.data_quality.missing_critical && narrative.data_quality.missing_critical.length > 0 && (
                        <div>
                          <span className="text-red-400 font-medium">Missing Critical Data:</span>
                          <ul className="mt-1 ml-4 list-disc text-terminal-text-dim">
                            {narrative.data_quality.missing_critical.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {narrative.data_quality.missing_important && narrative.data_quality.missing_important.length > 0 && (
                        <div>
                          <span className="text-yellow-400 font-medium">Missing Important Data:</span>
                          <ul className="mt-1 ml-4 list-disc text-terminal-text-dim">
                            {narrative.data_quality.missing_important.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="pt-2 border-t border-terminal-border space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-terminal-text-dim">Yield Curve:</span>
                          <span className={narrative.data_quality.yield_curve_available ? 'text-green-400' : 'text-red-400'}>
                            {narrative.data_quality.yield_curve_available ? '✓ Available' : '✗ Missing'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-terminal-text-dim">FX Data:</span>
                          <span className={narrative.data_quality.fx_data_available ? 'text-green-400' : 'text-red-400'}>
                            {narrative.data_quality.fx_data_available ? '✓ Available' : '✗ Missing'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-terminal-text-dim">Credit Spreads:</span>
                          <span className={narrative.data_quality.credit_data_available ? 'text-green-400' : 'text-red-400'}>
                            {narrative.data_quality.credit_data_available ? '✓ Available' : '✗ Missing'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-terminal-text-dim">News Health:</span>
                          <span className={
                            narrative.data_quality.news_health === 'GOOD' ? 'text-green-400' :
                            narrative.data_quality.news_health === 'DEGRADED' ? 'text-yellow-400' :
                            'text-red-400'
                          }>
                            {narrative.data_quality.news_health} ({narrative.data_quality.news_count} articles)
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Context Snapshot (Audit Trail) */}
            {narrative.context_snapshot && (
              <div className="mt-4 pt-4 border-t border-terminal-border">
                <button
                  onClick={() => setShowContextSnapshot(!showContextSnapshot)}
                  className="flex items-center gap-2 text-xs text-terminal-text-dim hover:text-terminal-text transition-colors"
                >
                  <ChevronDown className={`w-3 h-3 transition-transform ${showContextSnapshot ? 'rotate-180' : ''}`} />
                  <span>View Context Snapshot (Audit Trail)</span>
                </button>
                {showContextSnapshot && (
                  <div className="mt-3 p-4 bg-terminal-dark rounded-lg border border-terminal-border overflow-x-auto">
                    <pre className="text-xs text-terminal-text-dim font-mono whitespace-pre-wrap">
                      {narrative.context_snapshot}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
