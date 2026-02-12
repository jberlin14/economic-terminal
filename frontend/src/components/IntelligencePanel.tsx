import React, { useState, useEffect } from 'react';
import { Activity, BookOpen, GitCompare, AlertTriangle, ChevronDown, RefreshCw, Loader2, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface RegimeData {
  regime: string;
  active_shifts: any[];
  shift_count: number;
  critical_count: number;
  high_count: number;
  timestamp: string;
}

interface PlaybookData {
  current_conditions: any;
  matches: any[];
  best_match: any;
  ai_analysis?: string;
  timestamp: string;
}

interface CorrelationData {
  correlations: any[];
  breakdowns: any[];
  breakdown_count: number;
  pairs_tracked: number;
  timestamp: string;
}

type TabType = 'regime' | 'playbook' | 'correlations';

const REGIME_COLORS: Record<string, string> = {
  CRISIS: 'text-red-400 bg-red-500/20 border-red-500/30',
  RISK_OFF: 'text-orange-400 bg-orange-500/20 border-orange-500/30',
  CAUTIOUS: 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30',
  WATCHFUL: 'text-blue-400 bg-blue-500/20 border-blue-500/30',
  RISK_ON: 'text-green-400 bg-green-500/20 border-green-500/30',
};

export const IntelligencePanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('regime');
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [playbook, setPlaybook] = useState<PlaybookData | null>(null);
  const [correlations, setCorrelations] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState<Record<TabType, boolean>>({
    regime: false,
    playbook: false,
    correlations: false,
  });
  const [errors, setErrors] = useState<Record<TabType, string | null>>({
    regime: null,
    playbook: null,
    correlations: null,
  });

  useEffect(() => {
    fetchRegime();
  }, []);

  const fetchRegime = async () => {
    setLoading(prev => ({ ...prev, regime: true }));
    try {
      const res = await fetch(`${API_URL}/api/intelligence/regime`);
      if (!res.ok) throw new Error('Failed to fetch');
      setRegime(await res.json());
      setErrors(prev => ({ ...prev, regime: null }));
    } catch (err) {
      setErrors(prev => ({ ...prev, regime: err instanceof Error ? err.message : 'Error' }));
    } finally {
      setLoading(prev => ({ ...prev, regime: false }));
    }
  };

  const fetchPlaybook = async () => {
    if (playbook) return; // Already loaded
    setLoading(prev => ({ ...prev, playbook: true }));
    try {
      const res = await fetch(`${API_URL}/api/intelligence/playbook?with_analysis=true`);
      if (!res.ok) throw new Error('Failed to fetch');
      setPlaybook(await res.json());
      setErrors(prev => ({ ...prev, playbook: null }));
    } catch (err) {
      setErrors(prev => ({ ...prev, playbook: err instanceof Error ? err.message : 'Error' }));
    } finally {
      setLoading(prev => ({ ...prev, playbook: false }));
    }
  };

  const fetchCorrelations = async () => {
    if (correlations) return;
    setLoading(prev => ({ ...prev, correlations: true }));
    try {
      const res = await fetch(`${API_URL}/api/intelligence/correlations`);
      if (!res.ok) throw new Error('Failed to fetch');
      setCorrelations(await res.json());
      setErrors(prev => ({ ...prev, correlations: null }));
    } catch (err) {
      setErrors(prev => ({ ...prev, correlations: err instanceof Error ? err.message : 'Error' }));
    } finally {
      setLoading(prev => ({ ...prev, correlations: false }));
    }
  };

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    if (tab === 'playbook') fetchPlaybook();
    if (tab === 'correlations') fetchCorrelations();
  };

  const refreshCurrent = () => {
    if (activeTab === 'regime') { setRegime(null); fetchRegime(); }
    if (activeTab === 'playbook') { setPlaybook(null); fetchPlaybook(); }
    if (activeTab === 'correlations') { setCorrelations(null); fetchCorrelations(); }
  };

  return (
    <div className="bg-terminal-panel border border-terminal-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-cyan-900/30 to-transparent p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Shield className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="font-bold text-lg">Market Intelligence</h2>
              <p className="text-xs text-terminal-text-dim">Regime Detection / Playbook / Correlations</p>
            </div>
          </div>
          <button
            onClick={refreshCurrent}
            className="p-2 hover:bg-terminal-dark rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-terminal-text-dim" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4">
          {([
            { id: 'regime' as TabType, label: 'Regime', icon: Activity },
            { id: 'playbook' as TabType, label: 'Playbook', icon: BookOpen },
            { id: 'correlations' as TabType, label: 'Correlations', icon: GitCompare },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                activeTab === tab.id
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-terminal-text-dim hover:bg-terminal-dark border border-transparent'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Regime Tab */}
        {activeTab === 'regime' && (
          <div>
            {loading.regime && (
              <div className="flex items-center gap-2 text-terminal-text-dim py-8 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Scanning for regime shifts...</span>
              </div>
            )}

            {errors.regime && (
              <div className="text-red-400 text-sm py-4">{errors.regime}</div>
            )}

            {regime && !loading.regime && (
              <div className="space-y-4">
                {/* Regime Badge */}
                <div className="flex items-center gap-3">
                  <span className={`px-4 py-2 rounded-lg text-lg font-bold border ${REGIME_COLORS[regime.regime] || 'text-terminal-text bg-terminal-dark'}`}>
                    {regime.regime}
                  </span>
                  <div className="text-xs text-terminal-text-dim">
                    <div>{regime.shift_count} active signal{regime.shift_count !== 1 ? 's' : ''}</div>
                    {regime.critical_count > 0 && (
                      <div className="text-red-400">{regime.critical_count} CRITICAL</div>
                    )}
                  </div>
                </div>

                {/* Active Shifts */}
                {regime.active_shifts.length > 0 ? (
                  <div className="space-y-3">
                    {regime.active_shifts.map((shift, idx) => (
                      <div key={idx} className="p-3 bg-terminal-dark border border-terminal-border rounded-lg">
                        <div className="flex items-start justify-between mb-1">
                          <span className="font-medium text-sm">{shift.name}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            shift.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                          }`}>
                            {shift.severity}
                          </span>
                        </div>
                        <p className="text-xs text-terminal-text-dim">{shift.description}</p>
                        {shift.explanation && (
                          <p className="text-xs text-terminal-text mt-2 leading-relaxed border-t border-terminal-border pt-2">
                            {shift.explanation}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-terminal-text-dim text-sm">
                    No active regime shifts detected. Markets operating within normal parameters.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Playbook Tab */}
        {activeTab === 'playbook' && (
          <div>
            {loading.playbook && (
              <div className="flex items-center gap-2 text-terminal-text-dim py-8 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Matching historical episodes...</span>
              </div>
            )}

            {errors.playbook && (
              <div className="text-red-400 text-sm py-4">{errors.playbook}</div>
            )}

            {playbook && !loading.playbook && (
              <div className="space-y-4">
                {/* Current Conditions */}
                <div className="flex flex-wrap gap-2">
                  {playbook.current_conditions?.conditions && Object.entries(playbook.current_conditions.conditions).map(([key, val]) => (
                    <span
                      key={key}
                      className={`text-xs px-2 py-1 rounded border ${
                        val
                          ? 'bg-red-500/10 border-red-500/30 text-red-400'
                          : 'bg-terminal-dark border-terminal-border text-terminal-text-dim'
                      }`}
                    >
                      {key.replace(/_/g, ' ')} {val ? 'Y' : 'N'}
                    </span>
                  ))}
                </div>

                {/* AI Analysis */}
                {playbook.ai_analysis && (
                  <div className="p-3 bg-cyan-500/5 border border-cyan-500/20 rounded-lg">
                    <p className="text-sm leading-relaxed">{playbook.ai_analysis}</p>
                  </div>
                )}

                {/* Matches */}
                <div className="space-y-3">
                  {playbook.matches?.slice(0, 4).map((match: any, idx: number) => (
                    <div key={idx} className="p-3 bg-terminal-dark border border-terminal-border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm">{match.episode_name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-terminal-text-dim">{match.period}</span>
                          <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                            match.similarity_pct >= 70 ? 'bg-red-500/20 text-red-400' :
                            match.similarity_pct >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-terminal-dark text-terminal-text-dim'
                          }`}>
                            {match.similarity_pct}%
                          </span>
                        </div>
                      </div>

                      {/* Signal bars */}
                      <div className="flex gap-1 mb-2">
                        {match.matching_signals?.map((s: string) => (
                          <span key={s} className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded border border-green-500/20">
                            {s.replace(/_/g, ' ')}
                          </span>
                        ))}
                        {match.diverging_signals?.map((s: string) => (
                          <span key={s} className="text-[10px] px-1.5 py-0.5 bg-red-500/10 text-red-400 rounded border border-red-500/20">
                            {s.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>

                      <p className="text-xs text-terminal-text-dim leading-relaxed">
                        <span className="text-terminal-text font-medium">What followed: </span>
                        {match.what_followed}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Correlations Tab */}
        {activeTab === 'correlations' && (
          <div>
            {loading.correlations && (
              <div className="flex items-center gap-2 text-terminal-text-dim py-8 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Computing cross-asset correlations...</span>
              </div>
            )}

            {errors.correlations && (
              <div className="text-red-400 text-sm py-4">{errors.correlations}</div>
            )}

            {correlations && !loading.correlations && (
              <div className="space-y-4">
                {/* Breakdown Alert */}
                {correlations.breakdown_count > 0 && (
                  <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
                    <span className="text-sm text-orange-400">
                      {correlations.breakdown_count} correlation breakdown{correlations.breakdown_count > 1 ? 's' : ''} detected
                    </span>
                  </div>
                )}

                {/* Correlation Grid */}
                <div className="space-y-2">
                  {correlations.correlations?.map((corr: any) => (
                    <div
                      key={corr.pair_id}
                      className={`p-3 rounded-lg border ${
                        corr.is_breakdown
                          ? 'bg-orange-500/5 border-orange-500/30'
                          : 'bg-terminal-dark border-terminal-border'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">{corr.name}</span>
                        <div className="flex items-center gap-2">
                          {corr.is_breakdown && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-orange-500/20 text-orange-400 rounded">
                              BREAKDOWN
                            </span>
                          )}
                          <span className={`text-sm font-mono font-bold ${
                            corr.correlation_30d === null ? 'text-terminal-text-dim' :
                            Math.abs(corr.deviation_30d || 0) > 0.3 ? 'text-orange-400' : 'text-green-400'
                          }`}>
                            {corr.correlation_30d !== null ? corr.correlation_30d.toFixed(2) : 'N/A'}
                          </span>
                        </div>
                      </div>

                      <div className="text-xs text-terminal-text-dim">{corr.description}</div>

                      <div className="flex items-center gap-4 mt-2 text-xs">
                        <span className="text-terminal-text-dim">
                          Normal: <span className="text-terminal-text">{corr.normal_correlation}</span>
                        </span>
                        {corr.correlation_90d !== null && (
                          <span className="text-terminal-text-dim">
                            90d: <span className="text-terminal-text">{corr.correlation_90d.toFixed(2)}</span>
                          </span>
                        )}
                        {corr.deviation_30d !== null && (
                          <span className={`${Math.abs(corr.deviation_30d) > 0.3 ? 'text-orange-400' : 'text-terminal-text-dim'}`}>
                            Dev: {corr.deviation_30d > 0 ? '+' : ''}{corr.deviation_30d.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Breakdown Details */}
                {correlations.breakdowns?.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-terminal-border">
                    <h3 className="text-sm font-bold mb-3 text-orange-400">Breakdown Analysis</h3>
                    {correlations.breakdowns.map((bd: any, idx: number) => (
                      <div key={idx} className="p-3 bg-terminal-dark border border-terminal-border rounded-lg mb-2">
                        <div className="font-medium text-sm mb-1">{bd.pair}</div>
                        <p className="text-xs text-terminal-text-dim">{bd.explanation}</p>
                        <p className="text-xs text-orange-400 mt-1">{bd.significance}</p>
                      </div>
                    ))}
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
