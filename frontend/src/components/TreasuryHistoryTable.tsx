import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TENORS = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y', 'spread_10y2y'] as const;
type Tenor = typeof TENORS[number];

const TENOR_LABELS: Record<Tenor, string> = {
  '1M': '1M', '3M': '3M', '6M': '6M', '1Y': '1Y', '2Y': '2Y',
  '5Y': '5Y', '10Y': '10Y', '20Y': '20Y', '30Y': '30Y',
  'spread_10y2y': '10-2',
};

const HORIZONS = ['1D', '1W', '1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y'] as const;
type Horizon = typeof HORIZONS[number];

interface ChartPoint {
  date: string;
  value: number;
}

interface ChartData {
  tenor: string;
  horizon: string;
  current: number | null;
  change: number | null;
  unit: string;
  points: ChartPoint[];
}

export const TreasuryHistoryTable: React.FC = () => {
  const [tenor, setTenor] = useState<Tenor>('10Y');
  const [horizon, setHorizon] = useState<Horizon>('1M');
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async (t: Tenor, h: Horizon) => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/yields/tenor-chart?tenor=${t}&horizon=${h.toLowerCase()}`
      );
      if (res.ok) {
        setData(await res.json());
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(tenor, horizon);
  }, [tenor, horizon, fetchData]);

  // Pre-compute which tick values to show based on horizon and data
  const tickValues = useMemo(() => {
    if (!data?.points.length) return undefined;
    const points = data.points;

    if (['1D', '1W', '1M', '3M'].includes(horizon)) {
      // Let Recharts auto-pick ticks for short horizons
      return undefined;
    }

    const ticks: string[] = [];
    const seen = new Set<string>();

    for (const pt of points) {
      const d = new Date(pt.date);
      let key: string;

      if (horizon === '6M' || horizon === '1Y') {
        key = `${d.getFullYear()}-${d.getMonth()}`;
      } else if (horizon === '2Y') {
        const q = Math.ceil((d.getMonth() + 1) / 3);
        key = `${d.getFullYear()}-Q${q}`;
      } else {
        // 5Y, 10Y
        key = `${d.getFullYear()}`;
      }

      if (!seen.has(key)) {
        seen.add(key);
        ticks.push(pt.date); // Use the first data point for each period
      }
    }

    return ticks;
  }, [data?.points, horizon]);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    if (horizon === '1D') {
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }
    if (horizon === '1W') {
      return d.toLocaleDateString('en-US', { weekday: 'short' });
    }
    if (['1M', '3M'].includes(horizon)) {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    if (horizon === '6M' || horizon === '1Y') {
      if (d.getMonth() === 0) {
        return `Jan '${d.getFullYear().toString().slice(-2)}`;
      }
      return d.toLocaleDateString('en-US', { month: 'short' });
    }
    if (horizon === '2Y') {
      const q = Math.ceil((d.getMonth() + 1) / 3);
      return `Q${q} '${d.getFullYear().toString().slice(-2)}`;
    }
    // 5Y, 10Y
    return d.getFullYear().toString();
  };

  const isSpread = tenor === 'spread_10y2y';
  const unit = isSpread ? 'bps' : '%';

  // Use data that matches current selection (avoid showing stale values during load)
  const displayData = data && data.tenor === tenor && data.horizon === horizon.toLowerCase() ? data : null;

  const changeColor = displayData?.change !== null && displayData?.change !== undefined
    ? (displayData.change > 0 ? 'text-positive' : displayData.change < 0 ? 'text-negative' : 'text-terminal-text-dim')
    : 'text-terminal-text-dim';

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-4">
      {/* Header row: title + current value + change */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-bold flex items-center gap-2">
          <span>📊</span>
          <span>Treasury History</span>
        </h2>
        {displayData && displayData.current !== null && (
          <div className="flex items-center gap-3">
            <span className="font-mono text-lg font-bold">
              {isSpread
                ? `${displayData.current.toFixed(1)} bps`
                : `${displayData.current.toFixed(3)}%`
              }
            </span>
            {displayData.change !== null && (
              <span className={`font-mono text-sm flex items-center gap-1 ${changeColor}`}>
                {displayData.change > 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {displayData.change > 0 ? '+' : ''}{displayData.change.toFixed(2)} {unit}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="h-40">
        {loading && !displayData ? (
          <div className="h-full flex items-center justify-center text-terminal-text-dim text-sm">
            Loading...
          </div>
        ) : displayData && displayData.points.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayData.points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis
                dataKey="date"
                stroke="#8b92b0"
                tick={{ fill: '#8b92b0', fontSize: 10 }}
                tickFormatter={formatDate}
                ticks={tickValues}
                minTickGap={['5Y', '10Y'].includes(horizon) ? 60 : ['2Y'].includes(horizon) ? 50 : 40}
              />
              <YAxis
                stroke="#8b92b0"
                tick={{ fill: '#8b92b0', fontSize: 10 }}
                width={48}
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => isSpread ? `${v.toFixed(0)}` : `${v.toFixed(2)}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1f2e',
                  border: '1px solid #2d3548',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                labelStyle={{ color: '#e6e8f0' }}
                labelFormatter={(label: string) => new Date(label).toLocaleDateString('en-US', {
                  month: 'short', day: 'numeric', year: 'numeric'
                })}
                formatter={(value: number) => [
                  isSpread ? `${value.toFixed(1)} bps` : `${value.toFixed(3)}%`,
                  TENOR_LABELS[tenor]
                ]}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={isSpread ? '#22d3ee' : '#60a5fa'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: isSpread ? '#22d3ee' : '#60a5fa' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-terminal-text-dim text-sm">
            No data available for this selection
          </div>
        )}
      </div>

      {/* Selectors */}
      <div className="flex gap-1 mt-3 flex-wrap items-center">
        <span className="text-xs text-terminal-text-dim font-semibold mr-1">Yield:</span>
        {TENORS.map((t) => (
          <button
            key={t}
            onClick={() => setTenor(t)}
            className={`px-2 py-1 rounded text-xs font-mono font-bold transition-colors ${
              tenor === t
                ? (t === 'spread_10y2y' ? 'bg-chart-cyan/30 text-chart-cyan border border-chart-cyan/50' : 'bg-neutral text-white')
                : 'bg-terminal-dark text-terminal-text-dim hover:text-terminal-text border border-terminal-border'
            }`}
          >
            {TENOR_LABELS[t]}
          </button>
        ))}

        {/* Separator */}
        <span className="border-l border-terminal-border mx-1 h-5" />

        <span className="text-xs text-terminal-text-dim font-semibold mr-1">Horizon:</span>
        {/* Horizon selector */}
        {HORIZONS.map((h) => (
          <button
            key={h}
            onClick={() => setHorizon(h)}
            className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
              horizon === h
                ? 'bg-chart-purple/30 text-chart-purple border border-chart-purple/50'
                : 'bg-terminal-dark text-terminal-text-dim hover:text-terminal-text border border-terminal-border'
            }`}
          >
            {h}
          </button>
        ))}
      </div>
    </div>
  );
};
