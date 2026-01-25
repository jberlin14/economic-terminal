import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface FXRate {
  pair: string;
  rate: number;
  change_1h: number | null;
  change_24h: number | null;
  change_1w: number | null;
  change_ytd: number | null;
  sparkline: number[];
}

interface FXDashboardProps {
  rates: FXRate[];
}

export const FXDashboard: React.FC<FXDashboardProps> = ({ rates }) => {
  const getRiskClass = (change: number | null): string => {
    if (change === null) return 'border-terminal-border';
    const abs = Math.abs(change);
    if (abs >= 2.0) return 'border-critical bg-critical/10';
    if (abs >= 1.0) return 'border-warning bg-warning/10';
    return 'border-terminal-border';
  };

  const getChangeColor = (change: number | null): string => {
    if (change === null) return 'text-terminal-text-dim';
    return change >= 0 ? 'text-positive' : 'text-negative';
  };

  const formatChange = (change: number | null): string => {
    if (change === null) return 'N/A';
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
  };

  const formatRate = (pair: string, rate: number): string => {
    if (pair.includes('JPY') || pair.includes('ARS')) {
      return rate.toFixed(2);
    }
    if (pair.includes('TWD')) {
      return rate.toFixed(3);
    }
    return rate.toFixed(4);
  };

  // Sort by priority (USDX first, then by pair name)
  const sortedRates = [...rates].sort((a, b) => {
    if (a.pair === 'USDX') return -1;
    if (b.pair === 'USDX') return 1;
    return a.pair.localeCompare(b.pair);
  });

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>💱</span>
        <span>FX Rates</span>
        <span className="text-sm font-normal text-terminal-text-dim ml-auto">
          USD/XXX Convention
        </span>
      </h2>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {sortedRates.map((fx) => (
          <div
            key={fx.pair}
            className={`p-4 rounded-lg border-2 transition-all duration-300 ${getRiskClass(fx.change_1h)}`}
          >
            {/* Header */}
            <div className="flex justify-between items-start mb-2">
              <span className="text-lg font-bold font-mono">{fx.pair}</span>
              <span className={`flex items-center gap-1 text-sm ${getChangeColor(fx.change_1h)}`}>
                {fx.change_1h !== null && (
                  fx.change_1h >= 0 
                    ? <TrendingUp className="w-4 h-4" /> 
                    : <TrendingDown className="w-4 h-4" />
                )}
                <span>1H</span>
              </span>
            </div>
            
            {/* Rate */}
            <div className="text-2xl font-mono font-bold mb-3">
              {formatRate(fx.pair, fx.rate)}
            </div>
            
            {/* Changes Grid */}
            <div className="grid grid-cols-4 gap-2 text-xs font-mono">
              <div>
                <div className="text-terminal-text-dim">1H</div>
                <div className={getChangeColor(fx.change_1h)}>
                  {formatChange(fx.change_1h)}
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">24H</div>
                <div className={getChangeColor(fx.change_24h)}>
                  {formatChange(fx.change_24h)}
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">1W</div>
                <div className={getChangeColor(fx.change_1w)}>
                  {formatChange(fx.change_1w)}
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">YTD</div>
                <div className={getChangeColor(fx.change_ytd)}>
                  {formatChange(fx.change_ytd)}
                </div>
              </div>
            </div>
            
            {/* Mini Sparkline */}
            {fx.sparkline && fx.sparkline.length > 0 && (
              <div className="mt-3 h-8">
                <MiniSparkline 
                  data={fx.sparkline} 
                  color={fx.change_24h && fx.change_24h >= 0 ? '#10b981' : '#ef4444'} 
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Simple SVG sparkline
const MiniSparkline: React.FC<{ data: number[]; color: string }> = ({ data, color }) => {
  if (!data || data.length < 2) return null;
  
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  
  const width = 100;
  const height = 30;
  const padding = 2;
  
  const points = data.map((value, index) => {
    const x = padding + (index / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((value - min) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};
