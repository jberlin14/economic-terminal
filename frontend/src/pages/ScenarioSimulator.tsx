import React, { useEffect, useState, useCallback } from 'react';
import {
  Zap, ArrowRight, AlertCircle, TrendingUp, TrendingDown, Minus,
  ChevronDown, BookOpen, Send, Loader2, Target, GitBranch, Clock,
  BarChart3, Shield,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

interface Preset {
  id: string;
  label: string;
  category: string;
}

interface Impact {
  asset_class: string;
  direction: 'up' | 'down' | 'unchanged';
  magnitude: string;
  confidence: 'high' | 'medium' | 'low';
  reasoning: string;
}

interface CascadeStep {
  step: number;
  from: string;
  to: string;
  mechanism: string;
  timeframe: string;
}

interface RegimeShift {
  probability: string;
  current: string;
  projected: string;
  reasoning: string;
}

interface TheoryApplied {
  key: string;
  name: string;
}

interface AnalyticalLens {
  depth_tier: string;
  tier_name: string;
  tier_description: string;
  theories_applied: TheoryApplied[];
  theory_count: number;
}

interface SimulationResult {
  scenario_summary: string;
  scenario_input: string;
  simulated_impacts: Impact[];
  cascade_chain: CascadeStep[];
  regime_shift: RegimeShift;
  historical_parallel: string;
  narrative: string;
  current_regime: string;
  analytical_lens?: AnalyticalLens;
  tokens_used: number;
  elapsed_ms: number;
  error?: string;
  parse_error?: boolean;
}

// ──────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────

const DEPTH_TIERS: Record<string, { name: string; description: string }> = {
  executive: { name: 'Executive Brief', description: 'C-suite conclusions' },
  analyst: { name: 'Analyst', description: 'Frameworks applied' },
  research: { name: 'Research', description: 'Full academic depth' },
};

const CATEGORY_COLORS: Record<string, string> = {
  inflation: 'border-orange-500/40 text-orange-400 bg-orange-500/10 hover:bg-orange-500/20',
  fed: 'border-blue-500/40 text-blue-400 bg-blue-500/10 hover:bg-blue-500/20',
  fx: 'border-purple-500/40 text-purple-400 bg-purple-500/10 hover:bg-purple-500/20',
  credit: 'border-red-500/40 text-red-400 bg-red-500/10 hover:bg-red-500/20',
  geopolitical: 'border-amber-500/40 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20',
  labor: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10 hover:bg-cyan-500/20',
  growth: 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20',
};

const REGIME_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  RISK_ON: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  CAUTIOUS: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
  RISK_OFF: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
  CRISIS: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30' },
};

const TIMEFRAME_COLORS: Record<string, string> = {
  immediate: 'text-red-400 bg-red-500/10',
  'short-term': 'text-amber-400 bg-amber-500/10',
  'medium-term': 'text-blue-400 bg-blue-500/10',
};

// ──────────────────────────────────────────────
// Small components
// ──────────────────────────────────────────────

const DirectionBadge: React.FC<{ direction: string; magnitude: string }> = ({ direction, magnitude }) => {
  const icon = direction === 'up' ? <TrendingUp size={14} /> : direction === 'down' ? <TrendingDown size={14} /> : <Minus size={14} />;
  const color = direction === 'up' ? 'text-positive' : direction === 'down' ? 'text-negative' : 'text-terminal-text-dim';
  return (
    <div className={`flex items-center gap-1.5 font-mono font-bold text-sm ${color}`}>
      {icon}
      <span>{magnitude}</span>
    </div>
  );
};

const ConfidenceMeter: React.FC<{ level: string }> = ({ level }) => {
  const bars = level === 'high' ? 3 : level === 'medium' ? 2 : 1;
  const color = level === 'high' ? 'bg-positive' : level === 'medium' ? 'bg-warning' : 'bg-terminal-text-dim';
  return (
    <div className="flex items-center gap-0.5" title={`${level} confidence`}>
      {[1, 2, 3].map(i => (
        <div key={i} className={`w-1 rounded-full ${i <= bars ? color : 'bg-terminal-border'}`} style={{ height: `${8 + i * 3}px` }} />
      ))}
      <span className="text-[9px] text-terminal-text-dim ml-1 uppercase font-mono">{level}</span>
    </div>
  );
};

const RegimeBadge: React.FC<{ regime: string; size?: 'sm' | 'md' }> = ({ regime, size = 'sm' }) => {
  const rc = REGIME_COLORS[regime] || { bg: 'bg-terminal-border', text: 'text-terminal-text-dim', border: 'border-terminal-border' };
  const sizing = size === 'md' ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-xs';
  return (
    <span className={`${rc.bg} ${rc.text} ${rc.border} border rounded font-bold font-mono ${sizing}`}>
      {regime.replace('_', ' ')}
    </span>
  );
};

const TimeframePill: React.FC<{ timeframe: string }> = ({ timeframe }) => {
  const color = TIMEFRAME_COLORS[timeframe] || 'text-terminal-text-dim bg-terminal-border';
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase ${color}`}>
      {timeframe}
    </span>
  );
};

// ──────────────────────────────────────────────
// Section components
// ──────────────────────────────────────────────

const ImpactCard: React.FC<{ impact: Impact; index: number }> = ({ impact, index }) => {
  const borderColor = impact.direction === 'up' ? 'border-l-positive' :
                      impact.direction === 'down' ? 'border-l-negative' : 'border-l-terminal-text-dim';
  return (
    <div className={`bg-terminal-dark rounded-lg border border-terminal-border/50 border-l-[3px] ${borderColor} p-4`}>
      <div className="flex items-start justify-between mb-2">
        <h4 className="text-sm font-semibold text-terminal-text">{impact.asset_class}</h4>
        <ConfidenceMeter level={impact.confidence} />
      </div>
      <DirectionBadge direction={impact.direction} magnitude={impact.magnitude} />
      <p className="text-xs text-terminal-text-dim mt-2 leading-relaxed">{impact.reasoning}</p>
    </div>
  );
};

const CascadeTimeline: React.FC<{ chain: CascadeStep[] }> = ({ chain }) => (
  <div className="relative">
    {chain.map((step, i) => (
      <div key={i} className="flex gap-4 mb-1 last:mb-0">
        {/* Vertical connector */}
        <div className="flex flex-col items-center w-8 shrink-0">
          <div className="w-8 h-8 rounded-full bg-neutral/20 border border-neutral/40 flex items-center justify-center z-10">
            <span className="text-xs font-mono font-bold text-neutral">{step.step}</span>
          </div>
          {i < chain.length - 1 && (
            <div className="w-0.5 flex-1 bg-gradient-to-b from-neutral/40 to-terminal-border min-h-[20px]" />
          )}
        </div>
        {/* Content */}
        <div className="flex-1 pb-4">
          <div className="bg-terminal-dark rounded-lg p-3 border border-terminal-border/30">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-xs font-semibold text-terminal-text">{step.from}</span>
              <ArrowRight size={12} className="text-neutral shrink-0" />
              <span className="text-xs font-semibold text-terminal-text">{step.to}</span>
              <TimeframePill timeframe={step.timeframe} />
            </div>
            <p className="text-[11px] text-terminal-text-dim leading-relaxed">{step.mechanism}</p>
          </div>
        </div>
      </div>
    ))}
  </div>
);

const NarrativeBlock: React.FC<{ text: string }> = ({ text }) => {
  // Split into paragraphs and render with proper spacing
  const paragraphs = text.split('\n').filter(p => p.trim());
  return (
    <div className="space-y-3">
      {paragraphs.map((para, i) => (
        <p key={i} className="text-sm text-terminal-text leading-relaxed">
          {para.trim()}
        </p>
      ))}
    </div>
  );
};

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────

export const ScenarioSimulator: React.FC = () => {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [scenario, setScenario] = useState('');
  const [depthTier, setDepthTier] = useState('analyst');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLens, setShowLens] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/intelligence/scenario/presets`)
      .then(res => res.json())
      .then(data => setPresets(data.presets || []))
      .catch(() => {});
  }, []);

  const simulate = useCallback(async (scenarioText?: string) => {
    const text = scenarioText || scenario.trim();
    if (!text || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/api/intelligence/scenario/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: text, theory_depth: depthTier }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Simulation failed');
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [scenario, depthTier, loading]);

  const handlePresetClick = (preset: Preset) => {
    setScenario(preset.label);
    simulate(preset.label);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      simulate();
    }
  };

  return (
    <div className="container mx-auto px-4 py-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-neutral/20 border border-neutral/30 flex items-center justify-center">
          <Zap className="w-5 h-5 text-neutral" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-terminal-text">Scenario Simulator</h1>
          <p className="text-xs text-terminal-text-dim">Trace cascading market impact of hypothetical events</p>
        </div>
      </div>

      {/* Input Section */}
      <div className="bg-terminal-panel border border-terminal-border rounded-xl p-5 mb-6">
        {/* Preset Chips */}
        <div className="mb-4">
          <span className="text-[10px] text-terminal-text-dim mb-2 block uppercase tracking-wider font-mono">Quick Scenarios</span>
          <div className="flex flex-wrap gap-2">
            {presets.map(preset => (
              <button
                key={preset.id}
                onClick={() => handlePresetClick(preset)}
                disabled={loading}
                className={`px-3 py-1.5 rounded-lg text-xs border transition-all disabled:opacity-50 ${
                  CATEGORY_COLORS[preset.category] || 'border-terminal-border text-terminal-text-dim hover:bg-terminal-dark'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Input */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <input
            type="text"
            value={scenario}
            onChange={e => setScenario(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Or describe a custom scenario..."
            disabled={loading}
            className="flex-1 bg-terminal-dark text-terminal-text text-sm px-4 py-3 rounded-lg font-mono placeholder-terminal-text-dim/50 focus:outline-none focus:ring-2 focus:ring-neutral/50 border border-terminal-border"
          />

          <div className="flex items-center gap-2">
            <select
              value={depthTier}
              onChange={e => setDepthTier(e.target.value)}
              className="bg-terminal-dark text-terminal-text text-xs px-3 py-3 rounded-lg border border-terminal-border focus:outline-none"
            >
              {Object.entries(DEPTH_TIERS).map(([key, tier]) => (
                <option key={key} value={key}>{tier.name}</option>
              ))}
            </select>

            <button
              onClick={() => simulate()}
              disabled={loading || !scenario.trim()}
              className="px-5 py-3 bg-neutral hover:bg-blue-600 disabled:bg-terminal-border disabled:text-terminal-text-dim text-white rounded-lg transition-colors flex items-center gap-2 font-medium whitespace-nowrap"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Simulate
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-terminal-panel border border-terminal-border rounded-xl p-16 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-neutral/10 border border-neutral/20 mb-4">
            <Loader2 className="w-8 h-8 animate-spin text-neutral" />
          </div>
          <p className="text-terminal-text font-medium mb-1">Running simulation...</p>
          <p className="text-terminal-text-dim text-xs">Tracing cascading impacts across all asset classes</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-critical/10 border border-critical/30 rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-critical shrink-0" />
            <span className="text-critical text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Results — always render all sections for consistent layout */}
      {result && !loading && (
        <div className="space-y-5">
          {/* Scenario Summary Bar */}
          <div className="bg-terminal-panel border border-terminal-border rounded-xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Target size={18} className="text-neutral mt-0.5 shrink-0" />
                <div>
                  <h3 className="text-xs font-mono text-terminal-text-dim uppercase tracking-wider mb-1">Scenario</h3>
                  <p className="text-sm text-terminal-text font-medium leading-relaxed">
                    {result.scenario_summary || result.scenario_input}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-terminal-text-dim shrink-0 font-mono">
                <span>{(result.elapsed_ms / 1000).toFixed(1)}s</span>
                <span className="text-terminal-border">|</span>
                <span>{result.tokens_used?.toLocaleString()} tokens</span>
              </div>
            </div>
          </div>

          {/* Impact Grid — always show section */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 size={16} className="text-terminal-text-dim" />
              <h3 className="text-sm font-semibold text-terminal-text">Market Impact</h3>
            </div>
            {result.simulated_impacts && result.simulated_impacts.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {result.simulated_impacts.map((impact, i) => (
                  <ImpactCard key={i} impact={impact} index={i} />
                ))}
              </div>
            ) : (
              <div className="bg-terminal-panel border border-terminal-border rounded-xl p-4 text-xs text-terminal-text-dim italic">
                Impact data unavailable for this simulation.
              </div>
            )}
          </div>

          {/* Two Column: Cascade + Regime — always show both columns */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
            {/* Cascade Chain */}
            <div className="lg:col-span-3 bg-terminal-panel border border-terminal-border rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <GitBranch size={16} className="text-terminal-text-dim" />
                <h3 className="text-sm font-semibold text-terminal-text">Transmission Chain</h3>
              </div>
              {result.cascade_chain && result.cascade_chain.length > 0 ? (
                <CascadeTimeline chain={result.cascade_chain} />
              ) : (
                <p className="text-xs text-terminal-text-dim italic">Cascade data unavailable for this simulation.</p>
              )}
            </div>

            {/* Right column: Regime + Historical */}
            <div className="lg:col-span-2 space-y-5">
              {/* Regime Shift — always show */}
              <div className="bg-terminal-panel border border-terminal-border rounded-xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Shield size={16} className="text-terminal-text-dim" />
                  <h3 className="text-sm font-semibold text-terminal-text">Regime Impact</h3>
                </div>

                {result.regime_shift && (result.regime_shift.projected || result.regime_shift.reasoning) ? (
                  <>
                    <div className="flex items-center gap-3 mb-3">
                      <RegimeBadge regime={result.current_regime || result.regime_shift.current} size="md" />
                      <div className="flex items-center gap-1">
                        <div className="w-4 h-0.5 bg-terminal-border" />
                        <ArrowRight size={14} className="text-terminal-text-dim" />
                        <div className="w-4 h-0.5 bg-terminal-border" />
                      </div>
                      <RegimeBadge regime={result.regime_shift.projected} size="md" />
                    </div>

                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-[10px] text-terminal-text-dim uppercase font-mono">Probability:</span>
                      <span className={`text-xs font-bold font-mono ${
                        result.regime_shift.probability === 'high' ? 'text-critical' :
                        result.regime_shift.probability === 'medium' ? 'text-warning' :
                        result.regime_shift.probability === 'low' ? 'text-positive' :
                        'text-terminal-text-dim'
                      }`}>
                        {result.regime_shift.probability?.toUpperCase() || 'N/A'}
                      </span>
                    </div>

                    {result.regime_shift.reasoning && (
                      <p className="text-xs text-terminal-text-dim leading-relaxed">{result.regime_shift.reasoning}</p>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-terminal-text-dim italic">Regime shift data unavailable.</p>
                )}
              </div>

              {/* Historical Parallel — always show */}
              <div className="bg-terminal-panel border border-terminal-border rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Clock size={16} className="text-terminal-text-dim" />
                  <h3 className="text-sm font-semibold text-terminal-text">Historical Parallel</h3>
                </div>
                {result.historical_parallel ? (
                  <p className="text-xs text-terminal-text-dim leading-relaxed">{result.historical_parallel}</p>
                ) : (
                  <p className="text-xs text-terminal-text-dim italic">No historical parallel identified.</p>
                )}
              </div>
            </div>
          </div>

          {/* Full Narrative — always show */}
          <div className="bg-terminal-panel border border-terminal-border rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BookOpen size={16} className="text-terminal-text-dim" />
                <h3 className="text-sm font-semibold text-terminal-text">Analysis</h3>
              </div>

              {/* Analytical Lens Toggle */}
              {result.analytical_lens && result.analytical_lens.theory_count > 0 && (
                <button
                  onClick={() => setShowLens(!showLens)}
                  className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim hover:text-terminal-text transition-colors px-2 py-1 rounded-lg hover:bg-terminal-dark"
                >
                  <ChevronDown className={`w-3 h-3 transition-transform ${showLens ? 'rotate-180' : ''}`} />
                  <span>{result.analytical_lens.tier_name} · {result.analytical_lens.theory_count} frameworks</span>
                </button>
              )}
            </div>

            {/* Theory lens details */}
            {showLens && result.analytical_lens && (
              <div className="mb-4 p-3 bg-terminal-dark rounded-lg border border-terminal-border/30">
                <div className="flex flex-wrap gap-2">
                  {result.analytical_lens.theories_applied.map((t, i) => (
                    <span key={i} className="text-[10px] text-terminal-text-dim bg-terminal-panel px-2 py-1 rounded font-mono">
                      {t.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Narrative prose */}
            {result.narrative ? (
              <NarrativeBlock text={result.narrative} />
            ) : (
              <p className="text-xs text-terminal-text-dim italic">No narrative analysis available.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
