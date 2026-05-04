import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface RecessionProbability {
  trained: boolean;
  probabilities?: { '3m'?: number; '6m'?: number; '12m'?: number };
  raw_probabilities?: { '3m'?: number; '6m'?: number; '12m'?: number };
  signal_label?: string;
  signal?: 'low' | 'moderate' | 'high';
  message?: string;
  error?: string;
}

const SIGNAL_COLORS: Record<string, string> = {
  high: 'text-critical',
  moderate: 'text-warning',
  low: 'text-positive',
};

interface CellProps {
  horizon: '3m' | '6m' | '12m';
  label: string;
  probs: { '3m'?: number; '6m'?: number; '12m'?: number };
  raw: { '3m'?: number; '6m'?: number; '12m'?: number };
}

const Cell: React.FC<CellProps> = ({ horizon, label, probs, raw }) => {
  const calibrated = probs[horizon];
  const rawValue = raw[horizon];
  const showRaw =
    rawValue !== undefined &&
    calibrated !== undefined &&
    Math.abs(rawValue - calibrated) > 0.5;

  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-terminal-text-dim">
        {label}
      </span>
      <span className="text-2xl font-mono font-bold text-terminal-text leading-none mt-1">
        {calibrated !== undefined ? `${calibrated.toFixed(1)}%` : '—'}
      </span>
      {showRaw && rawValue !== undefined && (
        <span className="text-[10px] text-terminal-text-dim mt-1">
          raw {rawValue.toFixed(1)}%
        </span>
      )}
    </div>
  );
};

export const RecessionProbabilityCard: React.FC = () => {
  const [data, setData] = useState<RecessionProbability | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    fetch(`${API_URL}/api/intelligence/recession/probability`)
      .then((r) => r.json())
      .then((d: RecessionProbability) => {
        if (mounted) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
        <div className="text-terminal-text-dim text-sm animate-pulse">
          Loading recession probability…
        </div>
      </div>
    );
  }

  // Untrained or error state — show a hint and link to the model page.
  if (!data || !data.trained || !data.probabilities || data.error) {
    const note =
      data?.message ??
      data?.error ??
      'Recession model not available. Train it on the model page.';
    return (
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
        <div className="flex items-start gap-2 text-terminal-text-dim text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{note}</span>
        </div>
        <Link
          to="/recession-model"
          className="text-xs text-neutral hover:underline mt-2 inline-block"
        >
          Go to Recession Model →
        </Link>
      </div>
    );
  }

  const probs = data.probabilities ?? {};
  const raw = data.raw_probabilities ?? {};
  const signalColor = SIGNAL_COLORS[data.signal ?? 'low'];

  return (
    <Link
      to="/recession-model"
      className="block bg-terminal-panel border border-terminal-border rounded-lg p-4 hover:border-neutral transition-colors"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-neutral" />
          <h3 className="text-sm font-semibold text-terminal-text">
            Recession Probability
          </h3>
        </div>
        {data.signal_label && (
          <span className={`text-xs font-bold ${signalColor}`}>
            {data.signal_label}
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Cell horizon="3m" label="3 months" probs={probs} raw={raw} />
        <Cell horizon="6m" label="6 months" probs={probs} raw={raw} />
        <Cell horizon="12m" label="12 months" probs={probs} raw={raw} />
      </div>
      <div className="mt-3 text-[11px] text-terminal-text-dim">
        AI ensemble — calibrated probability. Click for full breakdown.
      </div>
    </Link>
  );
};
