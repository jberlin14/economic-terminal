import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, AlertCircle, Clock } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface NarrativeData {
  narrative: string;
  generated_at: string;
  model: string;
  tokens_used: number;
  indicators_count: number;
  news_count: number;
}

export const MarketNarrative: React.FC = () => {
  const [narrative, setNarrative] = useState<NarrativeData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState<boolean | null>(null);

  // Check if AI is available on mount
  useEffect(() => {
    checkAvailability();
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

  const generateNarrative = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/narrative/generate`, {
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
            <div className="mt-6 pt-4 border-t border-terminal-border flex items-center justify-between text-xs text-terminal-text-dim">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTimestamp(narrative.generated_at)}
                </span>
                <span>|</span>
                <span>{narrative.indicators_count} indicators</span>
                <span>|</span>
                <span>{narrative.news_count} news items</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                  Claude Sonnet 4
                </span>
                <span>{narrative.tokens_used.toLocaleString()} tokens</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
