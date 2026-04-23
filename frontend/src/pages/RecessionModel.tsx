import React, { useEffect, useState, useCallback } from 'react';
import {
  Brain, RefreshCw, AlertCircle, Info, ChevronDown, GitBranch,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea,
  CartesianGrid,
} from 'recharts';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

interface FeatureImportance { feature: string; coefficient?: number; importance?: number; }
interface ConfusionMatrix { true_positives: number; false_positives: number; true_negatives: number; false_negatives: number; }
interface SingleModelMetrics {
  accuracy: number; auc_roc: number; precision: number; recall: number;
  f1: number; specificity: number; balanced_accuracy: number;
  confusion_matrix: ConfusionMatrix;
  feature_importance?: FeatureImportance[];
}
interface TreeRule { conditions: string[]; recession_probability: number; samples: number; }
interface ModelInfo {
  trained: boolean;
  training_metadata?: {
    trained_at: string; data_start: string; data_end: string;
    n_samples: number; n_features: number; feature_names: string[];
    recession_rates: Record<string, number>;
    train_size: number; test_size: number;
    best_models?: Record<string, string>;
  };
  // metrics[horizon][model_type] = SingleModelMetrics
  metrics?: Record<string, Record<string, SingleModelMetrics>>;
  model_types?: Record<string, string>;
  best_model?: Record<string, string>;
  decision_tree_rules?: Record<string, TreeRule[]>;
  optimal_thresholds?: Record<string, Record<string, number>>;
  ensemble_weights?: Record<string, Record<string, number>>;
  horizons?: string[];
}
interface ProbabilityData {
  trained: boolean;
  probabilities?: Record<string, number>;
  model_probabilities?: Record<string, Record<string, number>>;
  signal?: string;
  signal_label?: string;
  feature_snapshot?: Record<string, number>;
  message?: string;
  error?: string;
}
interface HistoryData {
  trained: boolean;
  dates?: string[];
  prob_3m?: number[];
  prob_6m?: number[];
  prob_12m?: number[];
  actual_recession?: number[];
  error?: string;
}

const MODEL_LABELS: Record<string, string> = {
  logistic: 'Logistic Regression',
  knn: 'K-Nearest Neighbors',
  random_forest: 'Random Forest',
  gradient_boosting: 'Gradient Boosting',
};

const MODEL_COLORS: Record<string, string> = {
  logistic: '#3b82f6',
  knn: '#8b5cf6',
  random_forest: '#10b981',
  gradient_boosting: '#f59e0b',
};

// ──────────────────────────────────────────────
// Gauge Component
// ──────────────────────────────────────────────

const colorMap: Record<string, string> = { green: '#00d68f', yellow: '#ffb224', red: '#ff3b3b' };

const GaugeChart: React.FC<{ score: number; color: string; size?: number; label?: string }> = ({ score, color, size = 160, label }) => {
  const sw = 12, r = (size - sw) / 2, c = Math.PI * r;
  const offset = c - (Math.min(score, 100) / 100) * c;
  const stroke = colorMap[color] || '#3b82f6';

  return (
    <svg width={size} height={size / 2 + 28} viewBox={`0 0 ${size} ${size / 2 + 28}`}>
      <path d={`M ${sw/2} ${size/2} A ${r} ${r} 0 0 1 ${size - sw/2} ${size/2}`} fill="none" stroke="#1e293b" strokeWidth={sw} strokeLinecap="round" />
      <path d={`M ${sw/2} ${size/2} A ${r} ${r} 0 0 1 ${size - sw/2} ${size/2}`} fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset} style={{ transition: 'stroke-dashoffset 1s ease-out' }} />
      <text x={size/2} y={size/2 - 4} textAnchor="middle" fill="#e4eaf4" fontSize={size > 120 ? '32' : '20'} fontWeight="bold" fontFamily="JetBrains Mono, monospace">{Math.round(score)}%</text>
      <text x={size/2} y={size/2 + 16} textAnchor="middle" fill="#556882" fontSize={size > 120 ? '11' : '9'} fontFamily="Sora, sans-serif">{label}</text>
    </svg>
  );
};

const probColor = (pct: number): string => pct >= 50 ? 'red' : pct >= 25 ? 'yellow' : 'green';

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────

export const RecessionModel: React.FC = () => {
  const [probability, setProbability] = useState<ProbabilityData | null>(null);
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [trainingResult, setTrainingResult] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [showTreeRules, setShowTreeRules] = useState(false);
  const [comparisonHorizon, setComparisonHorizon] = useState<string>('6m');
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      const [probRes, infoRes] = await Promise.all([
        fetch(`${API_URL}/api/intelligence/recession/probability`),
        fetch(`${API_URL}/api/intelligence/recession/model-info`),
      ]);

      const probData = await probRes.json();
      const infoData = await infoRes.json();

      setProbability(probData);
      setModelInfo(infoData);

      if (probData.trained && !probData.error) {
        const histRes = await fetch(`${API_URL}/api/intelligence/recession/history`);
        const histData = await histRes.json();
        setHistory(histData);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleTrain = async () => {
    setTraining(true);
    setTrainingResult(null);
    try {
      const res = await fetch(`${API_URL}/api/intelligence/recession/train`, { method: 'POST' });
      const kickoff = await res.json();
      if (kickoff.status === 'already_training') {
        setTrainingResult('Training already in progress...');
      } else {
        setTrainingResult('Training 4 models across 3 horizons...');
      }

      const poll = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_URL}/api/intelligence/recession/training-status`);
          const status = await statusRes.json();

          if (status.status === 'training') {
            const elapsed = status.elapsed_seconds ? ` (${Math.round(status.elapsed_seconds)}s)` : '';
            setTrainingResult(`Training in progress${elapsed}...`);
          } else if (status.status === 'completed') {
            clearInterval(poll);
            setTrainingResult('All models trained successfully');
            setTraining(false);
            await fetchAll();
            setTimeout(() => setTrainingResult(null), 5000);
          } else if (status.status === 'failed') {
            clearInterval(poll);
            setTrainingResult(`Training failed: ${status.error || 'Unknown error'}`);
            setTraining(false);
            setTimeout(() => setTrainingResult(null), 8000);
          }
        } catch {
          // Polling error, keep trying
        }
      }, 2000);
    } catch (err) {
      setTrainingResult(err instanceof Error ? err.message : 'Training failed');
      setTraining(false);
      setTimeout(() => setTrainingResult(null), 5000);
    }
  };

  // Loading state
  if (loading && !probability) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-terminal-text text-xl animate-pulse">Loading Recession Model...</div>
      </div>
    );
  }

  // Error state
  if (error && !probability) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-critical mx-auto mb-3" />
          <p className="text-critical mb-3">{error}</p>
          <button onClick={fetchAll} className="px-4 py-2 bg-terminal-surface rounded text-sm text-terminal-text hover:bg-terminal-border transition-colors">Retry</button>
        </div>
      </div>
    );
  }

  // Not trained state
  if (probability && !probability.trained) {
    return (
      <div className="max-w-[1200px] mx-auto px-4 lg:px-6 py-4">
        <PageHeader
          onRefresh={fetchAll} loading={loading}
          showMethodology={showMethodology} setShowMethodology={setShowMethodology}
        />
        {showMethodology && <MethodologyPanel />}
        <div className="bg-terminal-panel border border-terminal-border rounded-lg p-12 text-center">
          <Brain className="w-16 h-16 text-terminal-text-dim mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-terminal-text mb-2">Model Not Trained</h2>
          <p className="text-sm text-terminal-text-dim max-w-md mx-auto mb-6">
            The recession model trains 4 classifiers (Logistic Regression, KNN, Random Forest, Gradient Boosting) on ~60 years of FRED data (43 series, 200+ features)
            across three forecast horizons (3, 6, 12 months). Predictions are an AUC-weighted ensemble with optimized thresholds.
          </p>
          <button onClick={handleTrain} disabled={training}
            className="px-6 py-3 bg-accent/20 border border-accent/40 rounded-lg text-accent font-medium hover:bg-accent/30 transition-colors disabled:opacity-50"
          >
            {training ? (
              <span className="flex items-center gap-2"><RefreshCw className="w-4 h-4 animate-spin" /> Training...</span>
            ) : (
              <span className="flex items-center gap-2"><Brain className="w-4 h-4" /> Train Models</span>
            )}
          </button>
          {trainingResult && <p className="mt-4 text-sm text-positive">{trainingResult}</p>}
        </div>
      </div>
    );
  }

  const probs = probability?.probabilities || {};
  const modelProbs = probability?.model_probabilities || {};
  const meta = modelInfo?.training_metadata;
  const metrics = modelInfo?.metrics;
  const bestModels = modelInfo?.best_model || {};
  const treeRules = modelInfo?.decision_tree_rules || {};

  // Build history chart data
  const chartData = history?.dates?.map((date, i) => ({
    date,
    label: new Date(date).toLocaleDateString('en-US', { year: '2-digit', month: 'short' }),
    prob_3m: history.prob_3m?.[i] ?? null,
    prob_6m: history.prob_6m?.[i] ?? null,
    prob_12m: history.prob_12m?.[i] ?? null,
    recession: history.actual_recession?.[i] ?? 0,
  })) || [];

  // Find recession periods for shading
  const recessionPeriods: { start: string; end: string }[] = [];
  let recStart: string | null = null;
  chartData.forEach((d, i) => {
    if (d.recession === 1 && !recStart) recStart = d.date;
    if (d.recession === 0 && recStart) {
      recessionPeriods.push({ start: recStart, end: chartData[i - 1]?.date || d.date });
      recStart = null;
    }
  });
  if (recStart) recessionPeriods.push({ start: recStart, end: chartData[chartData.length - 1]?.date || recStart });

  return (
    <div className="max-w-[1200px] mx-auto px-4 lg:px-6 py-4">
      <PageHeader
        onRefresh={fetchAll} loading={loading}
        showMethodology={showMethodology} setShowMethodology={setShowMethodology}
        onTrain={handleTrain} training={training} trainingResult={trainingResult}
      />

      {showMethodology && <MethodologyPanel />}

      {/* Ensemble Gauges */}
      <div className="bg-terminal-panel border border-terminal-border rounded-lg p-6 mb-4">
        <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-4 block">
          Ensemble Probability (AUC-Weighted Average of 4 Models)
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {[
            { key: '3m', label: '3-Month' },
            { key: '6m', label: '6-Month' },
            { key: '12m', label: '12-Month' },
          ].map(({ key, label }) => {
            const pct = probs[key] ?? 0;
            const c = probColor(pct);
            return (
              <div key={key} className="flex flex-col items-center">
                <GaugeChart score={pct} color={c} size={160} label={`${label} Horizon`} />
                <span className={`text-xs font-mono font-bold mt-1 ${c === 'green' ? 'text-positive' : c === 'yellow' ? 'text-warning' : 'text-critical'}`}>
                  {pct >= 50 ? 'Elevated' : pct >= 25 ? 'Moderate' : 'Low'} Risk
                </span>
              </div>
            );
          })}
        </div>

        {/* Per-model breakdown */}
        {Object.keys(modelProbs).length > 0 && (
          <div className="mt-4 pt-4 border-t border-terminal-border">
            <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-2 block">
              Individual Model Predictions
            </span>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-terminal-text-dim">
                    <th className="text-left py-1 pr-4">Model</th>
                    <th className="text-right py-1 px-2">3mo</th>
                    <th className="text-right py-1 px-2">6mo</th>
                    <th className="text-right py-1 px-2">12mo</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(modelProbs).map(([modelType, horizonProbs]) => (
                    <tr key={modelType} className="border-t border-terminal-border/30">
                      <td className="py-1.5 pr-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: MODEL_COLORS[modelType] || '#666' }} />
                        <span className="text-terminal-text">{MODEL_LABELS[modelType] || modelType}</span>
                      </td>
                      {['3m', '6m', '12m'].map(h => {
                        const v = horizonProbs[h] ?? 0;
                        return (
                          <td key={h} className={`text-right py-1.5 px-2 font-bold ${probColor(v) === 'red' ? 'text-critical' : probColor(v) === 'yellow' ? 'text-warning' : 'text-positive'}`}>
                            {v.toFixed(1)}%
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="border-t border-terminal-border">
                    <td className="py-1.5 pr-4 text-terminal-text font-bold">Ensemble</td>
                    {['3m', '6m', '12m'].map(h => {
                      const v = probs[h] ?? 0;
                      return (
                        <td key={h} className={`text-right py-1.5 px-2 font-bold ${probColor(v) === 'red' ? 'text-critical' : probColor(v) === 'yellow' ? 'text-warning' : 'text-positive'}`}>
                          {v.toFixed(1)}%
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Signal summary */}
        {probability?.signal_label && (
          <div className="text-center mt-4 pt-4 border-t border-terminal-border">
            <span className="text-xs text-terminal-text-dim">Ensemble 6-Month Signal: </span>
            <span className={`text-sm font-bold ${
              probability.signal === 'high' ? 'text-critical' :
              probability.signal === 'moderate' ? 'text-warning' : 'text-positive'
            }`}>
              {probability.signal_label}
            </span>
          </div>
        )}
      </div>

      {/* Historical Chart */}
      {chartData.length > 0 && (
        <div className="bg-terminal-panel border border-terminal-border rounded-lg p-6 mb-4">
          <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-3 block">
            Historical Ensemble Probability
          </span>
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="label" tick={{ fill: '#556882', fontSize: 9 }} tickLine={false} interval={Math.floor(chartData.length / 8)} />
                <YAxis domain={[0, 100]} tick={{ fill: '#556882', fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0d1521', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: '#8b92b0' }}
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name.replace('prob_', '').replace('m', '-mo')]}
                />
                {recessionPeriods.map((rp, i) => (
                  <ReferenceArea key={i} x1={rp.start} x2={rp.end} fill="#ef4444" fillOpacity={0.08} />
                ))}
                <ReferenceLine y={50} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.5} />
                <ReferenceLine y={25} stroke="#f59e0b" strokeDasharray="4 4" strokeOpacity={0.3} />
                <Area type="monotone" dataKey="prob_12m" stroke="#6366f1" fill="#6366f1" fillOpacity={0.05} strokeWidth={1} dot={false} name="12-mo" />
                <Area type="monotone" dataKey="prob_6m" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.08} strokeWidth={1.5} dot={false} name="6-mo" />
                <Area type="monotone" dataKey="prob_3m" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} strokeWidth={2} dot={false} name="3-mo" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-center gap-6 mt-2">
            <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim"><span className="w-3 h-0.5 bg-[#ef4444] inline-block" /> 3-month</span>
            <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim"><span className="w-3 h-0.5 bg-[#f59e0b] inline-block" /> 6-month</span>
            <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim"><span className="w-3 h-0.5 bg-[#6366f1] inline-block" /> 12-month</span>
            <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim"><span className="w-3 h-2 bg-[#ef4444]/10 inline-block" /> NBER Recession</span>
          </div>
        </div>
      )}

      {/* Decision Tree Logic (collapsible) */}
      {Object.keys(treeRules).length > 0 && (
        <div className="bg-terminal-panel border border-terminal-border rounded-lg overflow-hidden mb-4">
          <button
            onClick={() => setShowTreeRules(!showTreeRules)}
            className="w-full flex items-center justify-between p-4 hover:bg-terminal-surface/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <GitBranch size={14} className="text-emerald-400" />
              <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider">Decision Tree Logic</span>
            </div>
            <ChevronDown className={`w-4 h-4 text-terminal-text-dim transition-transform ${showTreeRules ? 'rotate-180' : ''}`} />
          </button>

          {showTreeRules && (
            <div className="p-4 pt-0 border-t border-terminal-border">
              <p className="text-[10px] text-terminal-text-dim mb-3">
                Key decision paths from the Random Forest model. These rules show the conditions that most strongly predict recession or expansion.
              </p>

              {/* Horizon tabs */}
              <div className="flex gap-1 mb-3">
                {['3m', '6m', '12m'].map(h => (
                  <button key={h} onClick={() => setComparisonHorizon(h)}
                    className={`px-3 py-1 rounded text-[10px] font-mono transition-colors ${
                      comparisonHorizon === h ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-terminal-text-dim hover:bg-terminal-surface'
                    }`}
                  >
                    {h.replace('m', '-mo')}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                {(treeRules[comparisonHorizon] || []).map((rule, i) => {
                  const isHighRisk = rule.recession_probability >= 50;
                  return (
                    <div key={i} className={`rounded-lg p-3 border ${
                      isHighRisk ? 'bg-red-500/5 border-red-500/20' : 'bg-emerald-500/5 border-emerald-500/20'
                    }`}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className={`text-xs font-mono font-bold ${isHighRisk ? 'text-critical' : 'text-positive'}`}>
                          {rule.recession_probability}% recession probability
                        </span>
                        <span className="text-[10px] text-terminal-text-dim font-mono">
                          {rule.samples} samples
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {rule.conditions.map((cond, j) => (
                          <span key={j} className="text-[10px] font-mono px-2 py-0.5 rounded bg-terminal-surface text-terminal-text">
                            {cond}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {(!treeRules[comparisonHorizon] || treeRules[comparisonHorizon].length === 0) && (
                  <p className="text-xs text-terminal-text-dim">No decision rules available for this horizon. Train the model to generate rules.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Model Comparison (collapsible) */}
      {metrics && (
        <div className="bg-terminal-panel border border-terminal-border rounded-lg overflow-hidden mb-4">
          <button
            onClick={() => setShowComparison(!showComparison)}
            className="w-full flex items-center justify-between p-4 hover:bg-terminal-surface/50 transition-colors"
          >
            <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider">Model Comparison & Performance</span>
            <ChevronDown className={`w-4 h-4 text-terminal-text-dim transition-transform ${showComparison ? 'rotate-180' : ''}`} />
          </button>

          {showComparison && (
            <div className="p-4 pt-0 border-t border-terminal-border">
              {/* Horizon tabs */}
              <div className="flex gap-1 mb-4">
                {['3m', '6m', '12m'].map(h => (
                  <button key={h} onClick={() => setComparisonHorizon(h)}
                    className={`px-3 py-1 rounded text-[10px] font-mono transition-colors ${
                      comparisonHorizon === h ? 'bg-accent/20 text-accent border border-accent/30' : 'text-terminal-text-dim hover:bg-terminal-surface'
                    }`}
                  >
                    {h.replace('m', '-mo')}
                  </button>
                ))}
              </div>

              {/* Summary Table */}
              <ComparisonTable
                metrics={metrics[comparisonHorizon] || {}}
                bestModel={bestModels[comparisonHorizon] || ''}
                ensembleWeights={modelInfo?.ensemble_weights?.[comparisonHorizon] || {}}
              />

              {/* Confusion Matrices */}
              <div className="mt-4">
                <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-2 block">
                  Confusion Matrices
                </span>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {Object.entries(metrics[comparisonHorizon] || {}).map(([modelType, m]) => (
                    <ConfusionMatrixCard key={modelType} modelType={modelType} cm={m.confusion_matrix} />
                  ))}
                </div>
              </div>

              {/* Feature Importance (best model for this horizon) */}
              <FeatureImportanceChart metrics={metrics[comparisonHorizon] || {}} bestModel={bestModels[comparisonHorizon] || 'random_forest'} />

              {/* Training metadata */}
              {meta && (
                <div className="mt-4 pt-4 border-t border-terminal-border">
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-[10px] text-terminal-text-dim font-mono">
                    <span>Trained: {new Date(meta.trained_at).toLocaleDateString()}</span>
                    <span>Data: {meta.data_start?.slice(0, 10)} to {meta.data_end?.slice(0, 10)}</span>
                    <span>Train: {meta.train_size?.toLocaleString()} / Test: {meta.test_size?.toLocaleString()}</span>
                    <span>Features: {meta.n_features}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ──────────────────────────────────────────────
// Comparison Table
// ──────────────────────────────────────────────

const METRIC_KEYS = [
  { key: 'f1', label: 'F-Score' },
  { key: 'accuracy', label: 'Accuracy' },
  { key: 'precision', label: 'Precision' },
  { key: 'recall', label: 'Recall' },
  { key: 'specificity', label: 'Specificity' },
  { key: 'balanced_accuracy', label: 'Balanced Acc' },
  { key: 'auc_roc', label: 'AUC-ROC' },
] as const;

const ComparisonTable: React.FC<{
  metrics: Record<string, SingleModelMetrics>;
  bestModel: string;
  ensembleWeights?: Record<string, number>;
}> = ({ metrics, bestModel, ensembleWeights = {} }) => {
  const modelTypes = Object.keys(metrics);
  if (modelTypes.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-terminal-text-dim border-b border-terminal-border">
            <th className="text-left py-2 pr-4">Metric</th>
            {modelTypes.map(mt => (
              <th key={mt} className="text-right py-2 px-2">
                <div className="flex items-center justify-end gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODEL_COLORS[mt] || '#666' }} />
                  <span>{(MODEL_LABELS[mt] || mt).split(' ').map(w => w[0]).join('')}</span>
                  {mt === bestModel && <span className="text-[8px] text-positive">BEST</span>}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRIC_KEYS.map(({ key, label }) => {
            const values = modelTypes.map(mt => (metrics[mt] as any)?.[key] ?? 0);
            const maxVal = Math.max(...values);

            return (
              <tr key={key} className="border-t border-terminal-border/30">
                <td className="py-1.5 pr-4 text-terminal-text-dim">{label}</td>
                {modelTypes.map((mt, i) => {
                  const v = values[i];
                  const isMax = v === maxVal && v > 0;
                  return (
                    <td key={mt} className={`text-right py-1.5 px-2 font-bold ${
                      isMax ? 'text-positive' : v >= 0.8 ? 'text-terminal-text' : v >= 0.6 ? 'text-warning' : 'text-critical'
                    }`}>
                      {(v * 100).toFixed(1)}%
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {/* Optimal threshold row */}
          <tr className="border-t border-terminal-border/30">
            <td className="py-1.5 pr-4 text-terminal-text-dim">Opt. Threshold</td>
            {modelTypes.map(mt => {
              const t = (metrics[mt] as any)?.optimal_threshold;
              return (
                <td key={mt} className="text-right py-1.5 px-2 text-accent font-bold">
                  {t != null ? t.toFixed(2) : '0.50'}
                </td>
              );
            })}
          </tr>
          {/* Ensemble weight row */}
          <tr className="border-t border-terminal-border/30">
            <td className="py-1.5 pr-4 text-terminal-text-dim">Ensemble Wt</td>
            {modelTypes.map(mt => {
              const w = ensembleWeights[mt];
              return (
                <td key={mt} className="text-right py-1.5 px-2 text-terminal-text font-bold">
                  {w != null ? `${(w * 100).toFixed(1)}%` : '25.0%'}
                </td>
              );
            })}
          </tr>
          {/* Confusion matrix summary row */}
          <tr className="border-t border-terminal-border">
            <td className="py-1.5 pr-4 text-terminal-text-dim">TP / FP / TN / FN</td>
            {modelTypes.map(mt => {
              const cm = metrics[mt]?.confusion_matrix;
              if (!cm) return <td key={mt} className="text-right py-1.5 px-2">-</td>;
              return (
                <td key={mt} className="text-right py-1.5 px-2 text-terminal-text-dim">
                  {cm.true_positives}/{cm.false_positives}/{cm.true_negatives}/{cm.false_negatives}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
};

// ──────────────────────────────────────────────
// Confusion Matrix Card
// ──────────────────────────────────────────────

const ConfusionMatrixCard: React.FC<{
  modelType: string;
  cm: ConfusionMatrix;
}> = ({ modelType, cm }) => {
  if (!cm) return null;

  return (
    <div className="bg-terminal-surface rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODEL_COLORS[modelType] || '#666' }} />
        <span className="text-[10px] font-mono font-bold text-terminal-text">
          {MODEL_LABELS[modelType] || modelType}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-0.5 text-[9px] font-mono">
        {/* Header */}
        <div className="text-terminal-text-dim" />
        <div className="text-center text-terminal-text-dim">Pred +</div>
        <div className="text-center text-terminal-text-dim">Pred -</div>
        {/* Actual + */}
        <div className="text-terminal-text-dim text-right pr-1">Act +</div>
        <div className="text-center py-1 rounded bg-positive/10 text-positive font-bold">{cm.true_positives}</div>
        <div className="text-center py-1 rounded bg-critical/10 text-critical font-bold">{cm.false_negatives}</div>
        {/* Actual - */}
        <div className="text-terminal-text-dim text-right pr-1">Act -</div>
        <div className="text-center py-1 rounded bg-critical/10 text-critical font-bold">{cm.false_positives}</div>
        <div className="text-center py-1 rounded bg-positive/10 text-positive font-bold">{cm.true_negatives}</div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────
// Feature Importance Chart
// ──────────────────────────────────────────────

const FeatureImportanceChart: React.FC<{
  metrics: Record<string, SingleModelMetrics>;
  bestModel: string;
}> = ({ metrics, bestModel }) => {
  // Prefer random_forest (has feature_importances_), fallback to bestModel, fallback to logistic
  const displayModel = metrics['random_forest']?.feature_importance
    ? 'random_forest'
    : metrics[bestModel]?.feature_importance
    ? bestModel
    : Object.keys(metrics).find(mt => metrics[mt]?.feature_importance) || '';

  const importances = metrics[displayModel]?.feature_importance;
  if (!importances || importances.length === 0) return null;

  const chartItems = importances.slice(0, 10).map(f => ({
    name: f.feature.replace(/_/g, ' ').replace(/([a-z])(\d)/g, '$1 $2'),
    value: Math.abs(f.coefficient ?? f.importance ?? 0),
    positive: (f.coefficient ?? 0) > 0,
    isCoeff: f.coefficient !== undefined,
  }));

  const isCoeffBased = chartItems[0]?.isCoeff;

  return (
    <div className="mt-4">
      <span className="text-[10px] text-terminal-text-dim font-mono uppercase tracking-wider mb-2 block">
        Feature Importance ({MODEL_LABELS[displayModel] || displayModel})
      </span>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartItems} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#556882', fontSize: 9 }} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ fill: '#8b92b0', fontSize: 9 }} width={120} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0d1521', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }}
              formatter={(value: number) => [value.toFixed(4), isCoeffBased ? 'Coefficient' : 'Importance']}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {chartItems.map((item, i) => (
                <Cell key={i} fill={isCoeffBased ? (item.positive ? '#ef4444' : '#00d68f') : MODEL_COLORS[displayModel] || '#3b82f6'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {isCoeffBased && (
        <div className="flex items-center justify-center gap-4 mt-2">
          <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim">
            <span className="w-2 h-2 rounded-sm bg-critical inline-block" /> Increases recession risk
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-terminal-text-dim">
            <span className="w-2 h-2 rounded-sm bg-positive inline-block" /> Decreases recession risk
          </span>
        </div>
      )}
    </div>
  );
};

// ──────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────

const PageHeader: React.FC<{
  onRefresh: () => void;
  loading: boolean;
  showMethodology: boolean;
  setShowMethodology: (v: boolean) => void;
  onTrain?: () => void;
  training?: boolean;
  trainingResult?: string | null;
}> = ({ onRefresh, loading, showMethodology, setShowMethodology, onTrain, training, trainingResult }) => (
  <div className="flex items-center justify-between mb-4">
    <div className="flex items-center gap-2.5">
      <div className="w-7 h-7 rounded-lg bg-purple-500/15 flex items-center justify-center">
        <Brain size={16} className="text-purple-400" />
      </div>
      <div>
        <h1 className="text-lg font-bold text-terminal-text">Recession Probability Model</h1>
        <p className="text-[10px] text-terminal-text-dim">Multi-model ensemble on 60+ years of FRED data</p>
      </div>
    </div>
    <div className="flex items-center gap-2">
      {trainingResult && (
        <span className="text-[10px] text-positive">{trainingResult}</span>
      )}
      {onTrain && (
        <button onClick={onTrain} disabled={training}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-sm transition-colors disabled:opacity-50"
        >
          {training ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Brain className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline text-xs">{training ? 'Training...' : 'Retrain'}</span>
        </button>
      )}
      <button
        onClick={() => setShowMethodology(!showMethodology)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-sm transition-colors ${
          showMethodology ? 'border-accent bg-accent/10 text-accent' : 'border-terminal-border hover:bg-terminal-surface text-terminal-text-dim'
        }`}
      >
        <Info size={14} />
        <span className="hidden sm:inline text-xs">Methodology</span>
      </button>
      <button onClick={onRefresh} disabled={loading}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-terminal-border hover:bg-terminal-surface text-sm text-terminal-text transition-colors"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        <span className="hidden sm:inline text-xs">Refresh</span>
      </button>
    </div>
  </div>
);

const MethodologyPanel: React.FC = () => (
  <div className="bg-terminal-panel border border-accent/30 rounded-lg p-5 mb-4">
    <h3 className="text-sm font-semibold text-terminal-text mb-3 flex items-center gap-2">
      <Info size={14} className="text-accent" /> How the Recession Model Works
    </h3>
    <div className="space-y-3 text-xs text-terminal-text-dim leading-relaxed">
      <p>
        This model trains <span className="text-terminal-text font-medium">four classifiers</span> on ~60 years of US economic data from FRED (back to 1960),
        each forecasting recession probability at 3, 6, and 12-month horizons. The ensemble probability is the average across all models.
      </p>
      <p>
        <span className="text-terminal-text font-medium">Models:</span>{' '}
        <span className="text-blue-400">Logistic Regression</span> (balanced class weights, baseline linear),{' '}
        <span className="text-purple-400">K-Nearest Neighbors</span> (distance-weighted, non-parametric),{' '}
        <span className="text-emerald-400">Random Forest</span> (balanced class weights, provides interpretable rules),{' '}
        <span className="text-amber-400">Gradient Boosting</span> (sequential tree ensemble, strong on imbalanced data).
      </p>
      <p>
        <span className="text-terminal-text font-medium">Training data:</span> NBER recession dates (USREC) provide labels. 21 FRED series spanning yield curve spreads,
        credit spreads (BAA-10Y), unemployment and Sahm Rule proxy, initial claims, nonfarm payrolls, industrial production, CPI inflation,
        fed funds rate, durable goods, building permits, housing starts, consumer sentiment, real personal income, consumer credit, M2 money supply,
        oil prices, and the OECD Leading Indicator. Each series is augmented with rolling averages, momentum, and year-over-year changes (~50+ features).
      </p>
      <p>
        <span className="text-terminal-text font-medium">Validation:</span> 60/40 time-ordered train/test split (no shuffling, no look-ahead bias).
        Class weights are balanced to handle the low recession base rate (~15% of months). Per-model optimal thresholds are tuned to maximize F1 score
        instead of using the default 0.5 cutoff, improving recall for recession detection.
      </p>
      <p>
        <span className="text-terminal-text font-medium">Ensemble:</span> The final probability is an AUC-weighted average across all models.
        Models with higher AUC (better discrimination) receive proportionally more weight in the ensemble, so strong performers
        dominate while weak models are downweighted automatically.
      </p>
      <p>
        <span className="text-terminal-text font-medium">Live predictions:</span> Current indicator values are pulled from the database with 12+ months of history
        to compute proper momentum and change features. Each model generates a probability, weighted by AUC performance.
      </p>
    </div>
  </div>
);
