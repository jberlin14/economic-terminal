import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Clock, ChevronRight, AlertCircle, RefreshCw, X } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

interface RegimePeriod {
  regime: string;
  start_date: string;
  end_date: string;
  days: number;
}

interface RegimeTransition {
  date: string;
  from_regime: string;
  to_regime: string;
  trigger_themes: string[];
}

interface JournalEntry {
  date: string;
  regime: string;
  key_themes: string[];
  narrative_summary: string | null;
  news_themes: Record<string, string[]>;
}

interface TimelineData {
  periods: RegimePeriod[];
  transitions: RegimeTransition[];
  entries: JournalEntry[];
  total_days: number;
  actual_days: number;
}

// ──────────────────────────────────────────────
// Regime Colors & Labels
// ──────────────────────────────────────────────

const REGIME_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  RISK_ON: { bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400', dot: 'bg-emerald-500' },
  CAUTIOUS: { bg: 'bg-amber-500/20', border: 'border-amber-500/40', text: 'text-amber-400', dot: 'bg-amber-500' },
  RISK_OFF: { bg: 'bg-orange-500/20', border: 'border-orange-500/40', text: 'text-orange-400', dot: 'bg-orange-500' },
  CRISIS: { bg: 'bg-red-500/20', border: 'border-red-500/40', text: 'text-red-400', dot: 'bg-red-500' },
  UNKNOWN: { bg: 'bg-gray-500/20', border: 'border-gray-500/40', text: 'text-gray-400', dot: 'bg-gray-500' },
};

const REGIME_BAR_COLORS: Record<string, string> = {
  RISK_ON: 'bg-emerald-500',
  CAUTIOUS: 'bg-amber-500',
  RISK_OFF: 'bg-orange-500',
  CRISIS: 'bg-red-500',
  UNKNOWN: 'bg-gray-500',
};

const REGIME_LABELS: Record<string, string> = {
  RISK_ON: 'Risk On',
  CAUTIOUS: 'Cautious',
  RISK_OFF: 'Risk Off',
  CRISIS: 'Crisis',
  UNKNOWN: 'Unknown',
};

// ──────────────────────────────────────────────
// Zoom Levels
// ──────────────────────────────────────────────

const ZOOM_LEVELS = [
  { key: '1W', label: '1W', days: 7 },
  { key: '1M', label: '1M', days: 30 },
  { key: '3M', label: '3M', days: 90 },
  { key: '6M', label: '6M', days: 180 },
  { key: '1Y', label: '1Y', days: 365 },
];

// ──────────────────────────────────────────────
// Theme Badge
// ──────────────────────────────────────────────

const ThemeBadge: React.FC<{ theme: string }> = ({ theme }) => {
  const label = theme.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const isNegative = ['inflation_hot', 'inflation_elevated', 'sahm_triggered', 'labor_softening',
    'curve_inverted', 'credit_elevated', 'credit_high', 'regime_crisis', 'regime_risk_off'].includes(theme);
  const isPositive = ['disinflation_progress', 'labor_stable', 'credit_normal', 'policy_accommodative'].includes(theme);

  const colorClass = isNegative ? 'text-critical bg-critical/10 border-critical/20' :
                     isPositive ? 'text-positive bg-positive/10 border-positive/20' :
                     'text-terminal-text-dim bg-terminal-border border-terminal-border';

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${colorClass}`}>
      {label}
    </span>
  );
};

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────

export const RegimeTimeline: React.FC = () => {
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState('3M');
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);
  const [hoveredTransition, setHoveredTransition] = useState<RegimeTransition | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);

  const zoomDays = ZOOM_LEVELS.find(z => z.key === zoomLevel)?.days || 90;

  const fetchTimeline = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/intelligence/regime/timeline?days=${zoomDays}`);
      if (!res.ok) throw new Error('Failed to fetch regime timeline');
      const result = await res.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [zoomDays]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // Scroll to end of timeline on load
  useEffect(() => {
    if (data && timelineRef.current) {
      timelineRef.current.scrollLeft = timelineRef.current.scrollWidth;
    }
  }, [data]);

  const handleEntryClick = (date: string) => {
    const entry = data?.entries.find(e => e.date === date);
    if (entry) {
      setSelectedEntry(selectedEntry?.date === date ? null : entry);
    }
  };

  if (loading && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-terminal-text text-xl animate-pulse">Loading Regime Timeline...</div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-critical mx-auto mb-3" />
          <div className="text-critical mb-4">{error}</div>
          <button onClick={fetchTimeline} className="px-4 py-2 bg-neutral rounded hover:bg-blue-600 text-white">Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const totalDays = data.entries.length || 1;
  const minBarWidth = 40; // minimum width for very short periods
  const dayWidth = Math.max(8, Math.min(80, 800 / totalDays)); // responsive day width

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 text-neutral" />
          <div>
            <h1 className="text-2xl font-bold text-terminal-text">Regime Timeline</h1>
            <p className="text-xs text-terminal-text-dim">
              {data.actual_days} days of regime history · {data.transitions.length} transitions
            </p>
          </div>
        </div>
        <button
          onClick={fetchTimeline}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded border border-terminal-border hover:bg-terminal-dark text-sm text-terminal-text transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Zoom Controls */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs text-terminal-text-dim mr-2">Zoom:</span>
        {ZOOM_LEVELS.map(level => (
          <button
            key={level.key}
            onClick={() => setZoomLevel(level.key)}
            className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
              zoomLevel === level.key
                ? 'bg-neutral text-white'
                : 'bg-terminal-panel text-terminal-text-dim hover:text-terminal-text border border-terminal-border'
            }`}
          >
            {level.label}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-4">
        {Object.entries(REGIME_LABELS).filter(([k]) => k !== 'UNKNOWN').map(([key, label]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded ${REGIME_BAR_COLORS[key]}`} />
            <span className="text-[11px] text-terminal-text-dim">{label}</span>
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
        {data.periods.length === 0 ? (
          <div className="text-center py-12 text-terminal-text-dim">
            <Clock className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p>No regime data available for this period.</p>
            <p className="text-xs mt-1">Run the daily journal scheduler to populate regime history.</p>
          </div>
        ) : (
          <>
            {/* Timeline Bar */}
            <div className="overflow-x-auto pb-2" ref={timelineRef}>
              <div className="flex items-stretch" style={{ minWidth: `${totalDays * dayWidth}px` }}>
                {data.periods.map((period, i) => {
                  const width = Math.max(minBarWidth, period.days * dayWidth);
                  const colors = REGIME_COLORS[period.regime] || REGIME_COLORS.UNKNOWN;
                  const isFirst = i === 0;
                  const isLast = i === data.periods.length - 1;

                  return (
                    <div key={i} className="relative flex-shrink-0" style={{ width: `${width}px` }}>
                      {/* Regime bar */}
                      <div
                        className={`h-12 ${REGIME_BAR_COLORS[period.regime] || REGIME_BAR_COLORS.UNKNOWN} opacity-80
                          ${isFirst ? 'rounded-l-lg' : ''} ${isLast ? 'rounded-r-lg' : ''}
                          cursor-pointer hover:opacity-100 transition-opacity flex items-center justify-center`}
                        onClick={() => handleEntryClick(period.start_date)}
                        title={`${REGIME_LABELS[period.regime]} · ${period.days}d · ${period.start_date} to ${period.end_date}`}
                      >
                        {width > 60 && (
                          <span className="text-[10px] font-mono text-white/80 truncate px-1">
                            {REGIME_LABELS[period.regime]}
                          </span>
                        )}
                      </div>

                      {/* Transition marker (diamond at boundary) */}
                      {!isLast && data.transitions[i] && (
                        <div
                          className="absolute -right-1.5 top-1/2 -translate-y-1/2 z-10 cursor-pointer"
                          onMouseEnter={() => setHoveredTransition(data.transitions[i])}
                          onMouseLeave={() => setHoveredTransition(null)}
                        >
                          <div className="w-3 h-3 bg-white rotate-45 border border-terminal-border shadow-lg" />
                        </div>
                      )}

                      {/* Date label */}
                      {(period.days >= 3 || width > 50) && (
                        <div className="text-[9px] text-terminal-text-dim text-center mt-1 font-mono truncate">
                          {new Date(period.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Transition Tooltip */}
            {hoveredTransition && (
              <div className="mt-3 p-3 bg-terminal-dark border border-terminal-border rounded-lg">
                <div className="flex items-center gap-2 text-xs">
                  <span className={REGIME_COLORS[hoveredTransition.from_regime]?.text || 'text-terminal-text'}>
                    {REGIME_LABELS[hoveredTransition.from_regime]}
                  </span>
                  <ChevronRight size={12} className="text-terminal-text-dim" />
                  <span className={REGIME_COLORS[hoveredTransition.to_regime]?.text || 'text-terminal-text'}>
                    {REGIME_LABELS[hoveredTransition.to_regime]}
                  </span>
                  <span className="text-terminal-text-dim ml-2">
                    {new Date(hoveredTransition.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                </div>
                {hoveredTransition.trigger_themes.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {hoveredTransition.trigger_themes.map((theme, i) => (
                      <ThemeBadge key={i} theme={theme} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Transition List */}
            {data.transitions.length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-terminal-text mb-3">Regime Transitions</h3>
                <div className="space-y-2">
                  {data.transitions.map((t, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 p-2 rounded hover:bg-terminal-dark cursor-pointer transition-colors"
                      onClick={() => handleEntryClick(t.date)}
                    >
                      <span className="text-xs text-terminal-text-dim font-mono w-20">
                        {new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                      <span className={`text-xs font-semibold ${REGIME_COLORS[t.from_regime]?.text || 'text-terminal-text'}`}>
                        {REGIME_LABELS[t.from_regime]}
                      </span>
                      <ChevronRight size={12} className="text-terminal-text-dim" />
                      <span className={`text-xs font-semibold ${REGIME_COLORS[t.to_regime]?.text || 'text-terminal-text'}`}>
                        {REGIME_LABELS[t.to_regime]}
                      </span>
                      {t.trigger_themes.length > 0 && (
                        <div className="flex gap-1 ml-2">
                          {t.trigger_themes.slice(0, 3).map((theme, j) => (
                            <ThemeBadge key={j} theme={theme} />
                          ))}
                          {t.trigger_themes.length > 3 && (
                            <span className="text-[10px] text-terminal-text-dim">+{t.trigger_themes.length - 3}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail Panel */}
      {selectedEntry && (
        <div className="mt-4 bg-terminal-panel border border-terminal-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <span className={`px-2 py-1 rounded text-xs font-bold ${
                REGIME_COLORS[selectedEntry.regime]?.bg || ''
              } ${REGIME_COLORS[selectedEntry.regime]?.text || ''}`}>
                {REGIME_LABELS[selectedEntry.regime]}
              </span>
              <span className="text-sm text-terminal-text font-mono">
                {new Date(selectedEntry.date).toLocaleDateString('en-US', {
                  weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
                })}
              </span>
            </div>
            <button
              onClick={() => setSelectedEntry(null)}
              className="p-1 hover:bg-terminal-dark rounded text-terminal-text-dim hover:text-terminal-text"
            >
              <X size={14} />
            </button>
          </div>

          {/* Themes */}
          {selectedEntry.key_themes.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {selectedEntry.key_themes.map((theme, i) => (
                <ThemeBadge key={i} theme={theme} />
              ))}
            </div>
          )}

          {/* Narrative */}
          {selectedEntry.narrative_summary && (
            <div className="text-xs text-terminal-text leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
              {selectedEntry.narrative_summary}
            </div>
          )}

          {!selectedEntry.narrative_summary && (
            <p className="text-xs text-terminal-text-dim italic">No narrative available for this date.</p>
          )}
        </div>
      )}
    </div>
  );
};
