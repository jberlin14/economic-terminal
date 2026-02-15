import React, { useEffect, useState, useCallback } from 'react';
import {
  Shield, TrendingUp, TrendingDown, Minus, RefreshCw, AlertCircle,
  Flame, Users, GitBranch, BarChart3, Activity, Globe, Info, ChevronDown,
} from 'lucide-react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

interface PillarComponent {
  label: string;
  value: string;
  status: string;
}

interface Pillar {
  id: string;
  name: string;
  score: number;
  color: string;
  trend: string;
  components: PillarComponent[];
  sparkline: (number | null)[];
  data_freshness: string | null;
}

interface ScorecardData {
  composite_score: number;
  composite_color: string;
  composite_trend: string;
  pillars: Pillar[];
  sparkline_dates: string[];
  composite_sparkline: number[];
  assessed_at: string;
  elapsed_ms: number;
}

// ──────────────────────────────────────────────
// Pillar Icons & Methodology
// ──────────────────────────────────────────────

const PILLAR_ICONS: Record<string, any> = {
  inflation: Flame,
  labor: Users,
  yield_curve: GitBranch,
  credit: BarChart3,
  volatility: Activity,
  geopolitical: Globe,
};

const PILLAR_METHODOLOGY: Record<string, { weight: string; description: string; inputs: string[]; scale: string }> = {
  inflation: {
    weight: '20%',
    description: 'Measures price pressure across consumer and producer prices. Higher scores signal purchasing power erosion and potential Fed tightening.',
    inputs: ['CPI Year-over-Year', 'CPI Trend (accelerating/stable/decelerating)', 'Core PCE Year-over-Year'],
    scale: '0 at 1.5% CPI, 50 at 3.5%, 100 at 6.0%+',
  },
  labor: {
    weight: '20%',
    description: 'Tracks employment health through recession indicators and payroll momentum. Rising scores suggest weakening job market conditions.',
    inputs: ['Sahm Rule (recession trigger at 0.50)', 'Unemployment Rate', 'Initial Jobless Claims', 'Nonfarm Payrolls MoM change'],
    scale: '0 at full employment, 50 at emerging stress, 100 at recessionary',
  },
  yield_curve: {
    weight: '15%',
    description: 'Monitors the Treasury yield curve shape and slope. Inversion historically precedes recessions by 12-18 months.',
    inputs: ['10Y-2Y Spread', 'Curve Shape (steep/normal/flat/inverted)', 'Steepening/Flattening Trend'],
    scale: '0 at steep (+2%), 50 at flat, 100 at deeply inverted',
  },
  credit: {
    weight: '15%',
    description: 'Assesses corporate bond market stress through investment-grade and high-yield spreads. Widening spreads signal deteriorating credit conditions.',
    inputs: ['Credit Stress Level', 'IG OAS (Option-Adjusted Spread)', 'HY OAS'],
    scale: '0 at tight spreads, 50 at normal, 100 at crisis-level widening',
  },
  volatility: {
    weight: '15%',
    description: 'Gauges market fear via the VIX index. Sustained elevation above 30 indicates significant stress; spikes above 40 signal panic.',
    inputs: ['VIX Level', 'VIX 1-Day Percentage Change'],
    scale: '<15 complacent, 15-25 normal, 25-35 elevated, 35+ crisis',
  },
  geopolitical: {
    weight: '15%',
    description: 'Uses market-based proxies for geopolitical risk rather than headline sentiment. Oil spikes, gold surges, and EM currency stress reveal real capital flows reacting to geopolitical events.',
    inputs: ['Crude Oil Price & Spike', 'Gold 1-Day Move (safe-haven demand)', 'EM FX Stress (capital flight)', 'Geopolitical News Count (tiebreaker)'],
    scale: 'Oil >$100 elevated, gold surge >2% stress, EM FX decline >1% concern',
  },
};

// ──────────────────────────────────────────────
// SVG Gauge Component
// ──────────────────────────────────────────────

const GaugeChart: React.FC<{ score: number; color: string; size?: number }> = ({
  score, color, size = 200,
}) => {
  const strokeWidth = 16;
  const radius = (size - strokeWidth) / 2;
  const circumference = Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const colorMap: Record<string, string> = {
    green: '#10b981',
    yellow: '#f59e0b',
    red: '#ef4444',
  };
  const strokeColor = colorMap[color] || '#3b82f6';

  return (
    <svg width={size} height={size / 2 + 36} viewBox={`0 0 ${size} ${size / 2 + 36}`}>
      {/* Background arc */}
      <path
        d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
        fill="none"
        stroke="#2d3548"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {/* Filled arc */}
      <path
        d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 1s ease-out' }}
      />
      {/* Score text */}
      <text x={size / 2} y={size / 2 - 6} textAnchor="middle" fill="#e6e8f0" fontSize="42" fontWeight="bold" fontFamily="JetBrains Mono, monospace">
        {Math.round(score)}
      </text>
      <text x={size / 2} y={size / 2 + 20} textAnchor="middle" fill="#8b92b0" fontSize="13" fontFamily="Inter, sans-serif">
        / 100
      </text>
    </svg>
  );
};

// ──────────────────────────────────────────────
// Trend Arrow
// ──────────────────────────────────────────────

const TrendIndicator: React.FC<{ trend: string }> = ({ trend }) => {
  if (trend === 'improving' || trend === 'decelerating') {
    return <span className="flex items-center gap-1 text-positive text-xs font-medium"><TrendingDown size={12} /> Improving</span>;
  }
  if (trend === 'deteriorating' || trend === 'accelerating') {
    return <span className="flex items-center gap-1 text-negative text-xs font-medium"><TrendingUp size={12} /> Worsening</span>;
  }
  return <span className="flex items-center gap-1 text-terminal-text-dim text-xs"><Minus size={12} /> Stable</span>;
};

// ──────────────────────────────────────────────
// Sparkline
// ──────────────────────────────────────────────

const MiniSparkline: React.FC<{ data: (number | null)[]; color: string }> = ({ data, color }) => {
  const filtered = data.filter((d): d is number => d !== null);
  if (filtered.length < 2) return null;

  const chartData = filtered.map((v) => ({ v }));
  const colorMap: Record<string, string> = {
    green: '#10b981',
    yellow: '#f59e0b',
    red: '#ef4444',
  };

  return (
    <div className="w-24 h-10">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={colorMap[color] || '#3b82f6'}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

// ──────────────────────────────────────────────
// Status Badge
// ──────────────────────────────────────────────

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colorClass = (() => {
    switch (status) {
      case 'on target':
      case 'healthy':
      case 'low':
      case 'strong':
      case 'normal':
      case 'complacent':
      case 'tight':
      case 'quiet':
      case 'steep':
      case 'steepening':
        return 'text-positive bg-positive/10';
      case 'moderate':
      case 'stable':
      case 'flat':
        return 'text-terminal-text-dim bg-terminal-border';
      case 'elevated':
      case 'softening':
      case 'stall speed':
      case 'inverted':
      case 'partially_inverted':
      case 'flattening':
      case 'wide':
      case 'active':
      case 'stress':
        return 'text-warning bg-warning/10';
      case 'high':
      case 'triggered':
      case 'recession signal':
      case 'contracting':
      case 'crisis':
      case 'spike':
      case 'stressed':
      case 'severe':
      case 'surge':
      case 'deeply_inverted':
        return 'text-critical bg-critical/10';
      default:
        return 'text-terminal-text-dim bg-terminal-border';
    }
  })();

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase tracking-wide ${colorClass}`}>
      {status}
    </span>
  );
};

// ──────────────────────────────────────────────
// Freshness Dot
// ──────────────────────────────────────────────

const FreshnessDot: React.FC<{ date: string | null }> = ({ date }) => {
  if (!date) return <span className="w-2 h-2 rounded-full bg-terminal-text-dim" title="No data" />;

  const now = new Date();
  const dataDate = new Date(date);
  const ageHours = (now.getTime() - dataDate.getTime()) / (1000 * 60 * 60);

  let color = 'bg-positive';
  let label = 'Fresh';
  if (ageHours > 72) {
    color = 'bg-critical';
    label = `${Math.floor(ageHours / 24)}d old`;
  } else if (ageHours > 24) {
    color = 'bg-warning';
    label = `${Math.floor(ageHours / 24)}d old`;
  }

  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-[10px] text-terminal-text-dim">{label}</span>
    </span>
  );
};

// ──────────────────────────────────────────────
// Score Bar (horizontal progress bar)
// ──────────────────────────────────────────────

const ScoreBar: React.FC<{ score: number; color: string }> = ({ score, color }) => {
  const colorMap: Record<string, string> = {
    green: 'bg-positive',
    yellow: 'bg-warning',
    red: 'bg-critical',
  };
  return (
    <div className="w-full h-1.5 bg-terminal-dark rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${colorMap[color] || 'bg-neutral'} transition-all duration-700`}
        style={{ width: `${Math.min(100, score)}%` }}
      />
    </div>
  );
};

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────

export const RiskScorecard: React.FC = () => {
  const [data, setData] = useState<ScorecardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);
  const [expandedPillar, setExpandedPillar] = useState<string | null>(null);

  const fetchScorecard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/intelligence/risk-scorecard`);
      if (!res.ok) throw new Error('Failed to fetch risk scorecard');
      const result = await res.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScorecard();
    const interval = setInterval(fetchScorecard, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchScorecard]);

  if (loading && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-terminal-text text-xl animate-pulse">Loading Risk Scorecard...</div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-critical mx-auto mb-3" />
          <div className="text-critical mb-4">{error}</div>
          <button onClick={fetchScorecard} className="px-4 py-2 bg-neutral rounded hover:bg-blue-600 text-white">Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const scoreLabel = data.composite_score <= 33 ? 'Low Risk' : data.composite_score <= 66 ? 'Moderate Risk' : 'High Risk';
  const scoreDescription = data.composite_score <= 33
    ? 'Market conditions are broadly favorable with limited stress signals across major risk pillars.'
    : data.composite_score <= 66
    ? 'Some risk indicators are elevated. Conditions warrant monitoring but do not signal imminent crisis.'
    : 'Multiple risk pillars are flashing warning signals. Elevated caution is warranted across portfolios.';

  return (
    <div className="container mx-auto px-4 py-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-neutral" />
          <div>
            <h1 className="text-2xl font-bold text-terminal-text">Macro Risk Scorecard</h1>
            <p className="text-xs text-terminal-text-dim">Weighted composite across 6 market-driven risk pillars</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data.elapsed_ms && (
            <span className="text-[10px] text-terminal-text-dim hidden sm:inline">{(data.elapsed_ms / 1000).toFixed(1)}s</span>
          )}
          <button
            onClick={() => setShowMethodology(!showMethodology)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-sm transition-colors ${
              showMethodology
                ? 'border-neutral bg-neutral/10 text-neutral'
                : 'border-terminal-border hover:bg-terminal-dark text-terminal-text-dim'
            }`}
          >
            <Info size={14} />
            <span className="hidden sm:inline">Methodology</span>
          </button>
          <button
            onClick={fetchScorecard}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 rounded border border-terminal-border hover:bg-terminal-dark text-sm text-terminal-text transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Methodology Panel */}
      {showMethodology && (
        <div className="bg-terminal-panel border border-neutral/30 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-terminal-text mb-3 flex items-center gap-2">
            <Info size={14} className="text-neutral" />
            How the Risk Score Works
          </h3>
          <div className="space-y-3 text-xs text-terminal-text-dim leading-relaxed">
            <p>
              The composite score is a <span className="text-terminal-text font-medium">weighted average</span> of 6 independent risk pillars, each scored 0-100 based on real market data and economic indicators.
              No AI or sentiment analysis is used — every score is derived from quantitative thresholds applied to observable data.
            </p>
            <div className="flex flex-wrap gap-4 py-2">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-positive" />
                <span><span className="text-positive font-mono font-medium">0-33</span> Low risk — conditions healthy</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-warning" />
                <span><span className="text-warning font-mono font-medium">34-66</span> Moderate risk — watch for deterioration</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-critical" />
                <span><span className="text-critical font-mono font-medium">67-100</span> High risk — multiple stress signals active</span>
              </div>
            </div>
            <p>
              Each pillar's weight reflects its importance for assessing macro risk. Trend indicators compare the current score
              against the 7-day-ago score to show whether conditions are improving or deteriorating. Sparklines reconstruct
              the last 14 days of scores from stored daily snapshots.
            </p>
          </div>
        </div>
      )}

      {/* Composite Score Hero Section */}
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-6 mb-6">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          {/* Gauge + Label */}
          <div className="flex flex-col items-center">
            <GaugeChart score={data.composite_score} color={data.composite_color} />
            <div className="flex items-center gap-3 mt-1">
              <span className={`text-lg font-bold ${
                data.composite_color === 'green' ? 'text-positive' :
                data.composite_color === 'yellow' ? 'text-warning' : 'text-critical'
              }`}>
                {scoreLabel}
              </span>
              <TrendIndicator trend={data.composite_trend} />
            </div>
            <p className="text-[11px] text-terminal-text-dim text-center mt-2 max-w-xs leading-relaxed">
              {scoreDescription}
            </p>
          </div>

          {/* Right side: Traffic Lights + Sparkline */}
          <div className="flex-1 flex flex-col gap-6 w-full">
            {/* Traffic Light Row */}
            <div>
              <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-3 block">Pillar Overview</span>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                {data.pillars.map(pillar => {
                  const Icon = PILLAR_ICONS[pillar.id] || Shield;
                  const dotColor = pillar.color === 'green' ? 'bg-positive' : pillar.color === 'yellow' ? 'bg-warning' : 'bg-critical';
                  const scoreColor = pillar.color === 'green' ? 'text-positive' : pillar.color === 'yellow' ? 'text-warning' : 'text-critical';
                  return (
                    <div key={pillar.id} className="flex flex-col items-center gap-1.5 p-2 rounded-lg bg-terminal-dark/50">
                      <div className={`w-6 h-6 rounded-full ${dotColor} flex items-center justify-center`}>
                        <Icon size={12} className="text-white" />
                      </div>
                      <span className="text-[10px] text-terminal-text-dim text-center leading-tight">{pillar.name}</span>
                      <span className={`text-xs font-mono font-bold ${scoreColor}`}>{Math.round(pillar.score)}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Composite Sparkline */}
            {data.composite_sparkline && data.composite_sparkline.length > 1 && (
              <div>
                <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-1 block">14-Day Composite Trend</span>
                <div className="w-full h-12">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.composite_sparkline.map(v => ({ v }))}>
                      <Line
                        type="monotone"
                        dataKey="v"
                        stroke={data.composite_color === 'green' ? '#10b981' : data.composite_color === 'yellow' ? '#f59e0b' : '#ef4444'}
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Pillar Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.pillars.map(pillar => {
          const Icon = PILLAR_ICONS[pillar.id] || Shield;
          const methodology = PILLAR_METHODOLOGY[pillar.id];
          const isExpanded = expandedPillar === pillar.id;
          const borderColor = pillar.color === 'green' ? 'border-positive/30' :
                             pillar.color === 'yellow' ? 'border-warning/30' : 'border-critical/30';
          const scoreColor = pillar.color === 'green' ? 'text-positive' :
                            pillar.color === 'yellow' ? 'text-warning' : 'text-critical';
          const scoreBg = pillar.color === 'green' ? 'bg-positive/10' :
                         pillar.color === 'yellow' ? 'bg-warning/10' : 'bg-critical/10';

          return (
            <div key={pillar.id} className={`bg-terminal-panel border ${borderColor} rounded-lg overflow-hidden`}>
              {/* Card Header */}
              <div className="p-4 pb-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-8 h-8 rounded-lg ${scoreBg} flex items-center justify-center`}>
                      <Icon size={16} className={scoreColor} />
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-terminal-text block">{pillar.name}</span>
                      {methodology && (
                        <span className="text-[10px] text-terminal-text-dim font-mono">Weight: {methodology.weight}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-2xl font-mono font-bold ${scoreColor}`}>
                      {Math.round(pillar.score)}
                    </span>
                  </div>
                </div>

                {/* Score Bar */}
                <ScoreBar score={pillar.score} color={pillar.color} />

                {/* Trend + Sparkline */}
                <div className="flex items-center justify-between mt-3">
                  <TrendIndicator trend={pillar.trend} />
                  <MiniSparkline data={pillar.sparkline} color={pillar.color} />
                </div>
              </div>

              {/* Components */}
              <div className="px-4 pb-3 space-y-2 border-t border-terminal-border/50 pt-3">
                {pillar.components.map((comp, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-[11px] text-terminal-text-dim">{comp.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-terminal-text font-mono font-medium">{comp.value}</span>
                      <StatusBadge status={comp.status} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Methodology Toggle + Freshness */}
              <div className="px-4 pb-3 pt-1 border-t border-terminal-border/30">
                <div className="flex items-center justify-between">
                  <FreshnessDot date={pillar.data_freshness} />
                  {methodology && (
                    <button
                      onClick={() => setExpandedPillar(isExpanded ? null : pillar.id)}
                      className="flex items-center gap-1 text-[10px] text-terminal-text-dim hover:text-terminal-text transition-colors"
                    >
                      <Info size={10} />
                      <span>How it's scored</span>
                      <ChevronDown size={10} className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    </button>
                  )}
                </div>

                {/* Expanded Methodology */}
                {isExpanded && methodology && (
                  <div className="mt-3 p-3 bg-terminal-dark rounded-lg text-[11px] text-terminal-text-dim leading-relaxed space-y-2">
                    <p>{methodology.description}</p>
                    <div>
                      <span className="text-terminal-text font-medium block mb-1">Inputs:</span>
                      <ul className="space-y-0.5 pl-3">
                        {methodology.inputs.map((input, i) => (
                          <li key={i} className="before:content-['·'] before:mr-1.5 before:text-terminal-text-dim">{input}</li>
                        ))}
                      </ul>
                    </div>
                    <p><span className="text-terminal-text font-medium">Scale:</span> {methodology.scale}</p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="mt-6 text-center text-[10px] text-terminal-text-dim">
        Last assessed: {new Date(data.assessed_at).toLocaleString('en-US', { timeZone: 'America/New_York' })} ET
      </div>
    </div>
  );
};
