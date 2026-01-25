import React from 'react';
import { TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

interface CreditSpread {
  index_name: string;
  spread_bps: number;
  percentile_90d: number | null;
  percentile_1y: number | null;
  avg_30d: number | null;
  avg_90d: number | null;
  change_1d: number | null;
  change_1w: number | null;
  timestamp: string;
}

interface CreditSpreadsPanelProps {
  spreads: CreditSpread[];
}

export const CreditSpreadsPanel: React.FC<CreditSpreadsPanelProps> = ({ spreads }) => {
  const getIndexLabel = (indexName: string): string => {
    const labels: Record<string, string> = {
      'US_IG': 'Investment Grade',
      'US_BBB': 'BBB Rated',
      'US_HY': 'High Yield',
      'US_HY_CCC': 'CCC & Below'
    };
    return labels[indexName] || indexName;
  };

  const getRiskClass = (percentile: number | null): string => {
    if (percentile === null) return 'border-terminal-border';
    if (percentile >= 95) return 'border-critical bg-critical/10';
    if (percentile >= 90) return 'border-warning bg-warning/10';
    if (percentile >= 75) return 'border-warning/50 bg-warning/5';
    return 'border-terminal-border';
  };

  const getPercentileColor = (percentile: number | null): string => {
    if (percentile === null) return 'text-terminal-text-dim';
    if (percentile >= 95) return 'text-critical';
    if (percentile >= 90) return 'text-warning';
    if (percentile >= 75) return 'text-yellow-400';
    return 'text-positive';
  };

  const getChangeColor = (change: number | null): string => {
    if (change === null) return 'text-terminal-text-dim';
    // For credit spreads, widening (positive change) is bad, tightening (negative) is good
    return change > 0 ? 'text-warning' : 'text-positive';
  };

  const formatChange = (change: number | null): string => {
    if (change === null) return 'N/A';
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}`;
  };

  const formatPercentile = (percentile: number | null): string => {
    if (percentile === null) return 'N/A';
    return `${percentile.toFixed(0)}th`;
  };

  // Sort by index type (IG, BBB, HY, HY_CCC)
  const sortedSpreads = [...spreads].sort((a, b) => {
    const order = ['US_IG', 'US_BBB', 'US_HY', 'US_HY_CCC'];
    return order.indexOf(a.index_name) - order.indexOf(b.index_name);
  });

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>📊</span>
        <span>Credit Spreads</span>
        <span className="text-sm font-normal text-terminal-text-dim ml-auto">
          ICE BofA OAS (bps)
        </span>
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {sortedSpreads.map((spread) => (
          <div
            key={spread.index_name}
            className={`p-4 rounded-lg border-2 transition-all duration-300 ${getRiskClass(spread.percentile_90d)}`}
          >
            {/* Header */}
            <div className="flex justify-between items-start mb-2">
              <div>
                <div className="text-xs text-terminal-text-dim uppercase tracking-wider">
                  {spread.index_name}
                </div>
                <div className="text-sm font-semibold mt-0.5">
                  {getIndexLabel(spread.index_name)}
                </div>
              </div>
              {spread.percentile_90d !== null && spread.percentile_90d >= 90 && (
                <AlertTriangle className="w-5 h-5 text-warning" />
              )}
            </div>

            {/* Spread Value */}
            <div className="text-2xl font-mono font-bold mb-3">
              {spread.spread_bps !== null && spread.spread_bps !== undefined ? spread.spread_bps.toFixed(2) : 'N/A'}
              <span className="text-sm text-terminal-text-dim ml-1">bps</span>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div>
                <div className="text-terminal-text-dim">90d Pctl</div>
                <div className={getPercentileColor(spread.percentile_90d)}>
                  {formatPercentile(spread.percentile_90d)}
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">Chg 1D</div>
                <div className={`flex items-center gap-0.5 ${getChangeColor(spread.change_1d)}`}>
                  {spread.change_1d !== null && (
                    spread.change_1d > 0
                      ? <TrendingUp className="w-3 h-3" />
                      : spread.change_1d < 0
                      ? <TrendingDown className="w-3 h-3" />
                      : null
                  )}
                  <span>{formatChange(spread.change_1d)}</span>
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">Avg 90D</div>
                <div className="text-terminal-text">
                  {spread.avg_90d !== null ? spread.avg_90d.toFixed(2) : 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-terminal-text-dim">vs Avg</div>
                <div className={spread.avg_90d !== null && spread.spread_bps !== null && spread.spread_bps !== undefined ? getChangeColor(spread.spread_bps - spread.avg_90d) : 'text-terminal-text-dim'}>
                  {spread.avg_90d !== null && spread.spread_bps !== null && spread.spread_bps !== undefined ? formatChange(spread.spread_bps - spread.avg_90d) : 'N/A'}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Market Status Indicator */}
      {sortedSpreads.length > 0 && (
        <div className="mt-4 pt-4 border-t border-terminal-border">
          <div className="flex items-center justify-between text-sm">
            <span className="text-terminal-text-dim">Credit Market Status:</span>
            <span className={getMarketStatusClass(sortedSpreads)}>
              {getMarketStatus(sortedSpreads)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

const getMarketStatus = (spreads: CreditSpread[]): string => {
  const highPercentile = spreads.some(s => s.percentile_90d !== null && s.percentile_90d >= 95);
  const elevatedPercentile = spreads.some(s => s.percentile_90d !== null && s.percentile_90d >= 90);

  if (highPercentile) return 'STRESSED';
  if (elevatedPercentile) return 'ELEVATED';
  return 'NORMAL';
};

const getMarketStatusClass = (spreads: CreditSpread[]): string => {
  const status = getMarketStatus(spreads);
  if (status === 'STRESSED') return 'text-critical font-semibold';
  if (status === 'ELEVATED') return 'text-warning font-semibold';
  return 'text-positive font-semibold';
};