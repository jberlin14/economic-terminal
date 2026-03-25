import React, { useState, useEffect, useRef } from 'react';
import {
  Activity, BookOpen, GitBranch, AlertTriangle, TrendingUp, TrendingDown, Minus, RefreshCw,
  Brain, Sparkles, MessageCircle, Send, RotateCcw, Clock, Zap, ChevronDown, BookOpenCheck, AlertCircle,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

type TabId = 'regime' | 'playbook' | 'correlations' | 'analysis' | 'chat';

interface RegimeShift {
  signal: string;
  signal_name: string;
  severity: string;
  value: number;
  description: string;
  ai_explanation?: string;
}

interface RegimeData {
  regime: string;
  regime_description: string;
  shifts: RegimeShift[];
  critical_count: number;
  high_count: number;
}

interface PlaybookMatch {
  episode_id: string;
  episode_name: string;
  period: string;
  similarity_pct: number;
  matching_signals: string[];
  diverging_signals: string[];
  matching_count: number;
  total_signals: number;
  what_followed: string;
}

interface PlaybookData {
  matches: PlaybookMatch[];
  ai_analysis?: string;
}

interface CorrelationPair {
  id: string;
  name: string;
  asset_a: string;
  asset_b: string;
  corr_30d: number | null;
  corr_90d: number | null;
  normal_range: number[];
  status: string;
  breakdown_detected: boolean;
  description: string;
  breakdown_meaning?: string;
  error?: string;
}

interface CorrelationData {
  pairs: CorrelationPair[];
  breakdowns_detected: number;
}

// AI Analysis types (from MarketNarrative)
interface DataQuality {
  quality_score: number;
  quality_level: string;
  indicators_available: number;
  indicators_expected: number;
  missing_critical: string[];
  missing_important: string[];
  yield_curve_available: boolean;
  fx_data_available: boolean;
  credit_data_available: boolean;
  news_count: number;
  news_health: string;
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

interface NarrativeData {
  narrative: string;
  generated_at: string;
  model: string;
  narrative_type?: string;
  narrative_mode?: string;
  tokens_used: number;
  indicators_count: number;
  news_count: number;
  context_snapshot?: string;
  market_regime?: string;
  from_cache?: boolean;
  cache_age_minutes?: number;
  data_quality?: DataQuality;
  is_fallback?: boolean;
  analytical_lens?: AnalyticalLens;
}

interface NarrativeMode {
  name: string;
  description: string;
  icon: string;
}

// Chat types (from ChatInterface)
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  tokens_used?: number;
  elapsed_ms?: number;
  analytical_lens?: AnalyticalLens;
}

interface DepthTier {
  name: string;
  description: string;
}

// ──────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────

const REGIME_COLORS: Record<string, string> = {
  CRISIS: 'bg-red-600',
  RISK_OFF: 'bg-orange-500',
  CAUTIOUS: 'bg-yellow-500',
  RISK_ON: 'bg-green-500',
};

const REGIME_TEXT_COLORS: Record<string, string> = {
  CRISIS: 'text-red-400',
  RISK_OFF: 'text-orange-400',
  CAUTIOUS: 'text-yellow-400',
  RISK_ON: 'text-green-400',
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'border-red-500 bg-red-500/10 text-red-400',
  HIGH: 'border-orange-500 bg-orange-500/10 text-orange-400',
  MEDIUM: 'border-yellow-500 bg-yellow-500/10 text-yellow-400',
  LOW: 'border-blue-500 bg-blue-500/10 text-blue-400',
};

const DEPTH_TIERS: Record<string, DepthTier> = {
  executive: { name: 'Executive Brief', description: 'C-suite conclusions' },
  analyst: { name: 'Analyst', description: 'Frameworks applied' },
  research: { name: 'Research', description: 'Full academic depth' },
};

const EXAMPLE_QUESTIONS = [
  "What's the current yield curve signaling?",
  "How are credit spreads trending?",
  "Is the labor market weakening?",
  "What's the Fed likely to do next?",
  "Summarize today's key market moves",
];

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────

export const IntelligencePanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('regime');

  // Intelligence data state
  const [regimeData, setRegimeData] = useState<RegimeData | null>(null);
  const [playbookData, setPlaybookData] = useState<PlaybookData | null>(null);
  const [correlationData, setCorrelationData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedMatch, setExpandedMatch] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // AI Analysis state (from MarketNarrative)
  const [narrative, setNarrative] = useState<NarrativeData | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);
  const [narrativeModes, setNarrativeModes] = useState<Record<string, NarrativeMode>>({});
  const [selectedMode, setSelectedMode] = useState<string>('comprehensive');
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [aiAvailable, setAiAvailable] = useState<boolean | null>(null);
  const [showDataQuality, setShowDataQuality] = useState(false);
  const [showAnalyticalLens, setShowAnalyticalLens] = useState(false);
  const [showContextSnapshot, setShowContextSnapshot] = useState(false);

  // Chat state (from ChatInterface)
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lastMetrics, setLastMetrics] = useState<{ tokens: number; ms: number } | null>(null);
  const [depthTier, setDepthTier] = useState<string>('analyst');
  const [showTierSelector, setShowTierSelector] = useState(false);
  const [expandedLens, setExpandedLens] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const tierSelectorRef = useRef<HTMLDivElement>(null);

  // Fetch intelligence data on mount
  useEffect(() => {
    fetchAllData();
    checkAiAvailability();
    fetchNarrativeModes();
  }, []);

  // Fetch tab data when switching (if not already loaded)
  useEffect(() => {
    if (activeTab === 'regime' && !regimeData) fetchTabData('regime');
    if (activeTab === 'playbook' && !playbookData) fetchTabData('playbook');
    if (activeTab === 'correlations' && !correlationData) fetchTabData('correlations');
  }, [activeTab]);

  // Auto-scroll chat messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus chat input when switching to chat tab
  useEffect(() => {
    if (activeTab === 'chat') chatInputRef.current?.focus();
  }, [activeTab]);

  // Close tier selector on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (tierSelectorRef.current && !tierSelectorRef.current.contains(e.target as Node)) {
        setShowTierSelector(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ──────────────────────────────────────────────
  // Intelligence Data Fetchers
  // ──────────────────────────────────────────────

  const fetchAllData = async () => {
    setRefreshing(true);
    setError(null);

    try {
      const [regimeRes, playbookRes, correlationsRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/intelligence/regime`),
        fetch(`${API_URL}/api/intelligence/playbook`),
        fetch(`${API_URL}/api/intelligence/correlations`),
      ]);

      if (regimeRes.status === 'fulfilled' && regimeRes.value.ok) {
        setRegimeData(await regimeRes.value.json());
      }
      if (playbookRes.status === 'fulfilled' && playbookRes.value.ok) {
        setPlaybookData(await playbookRes.value.json());
      }
      if (correlationsRes.status === 'fulfilled' && correlationsRes.value.ok) {
        setCorrelationData(await correlationsRes.value.json());
      }

      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setRefreshing(false);
    }
  };

  const fetchTabData = async (tab: 'regime' | 'playbook' | 'correlations') => {
    setLoading(true);
    setError(null);

    try {
      switch (tab) {
        case 'regime': {
          const res = await fetch(`${API_URL}/api/intelligence/regime`);
          if (!res.ok) throw new Error('Failed to fetch regime data');
          setRegimeData(await res.json());
          break;
        }
        case 'playbook': {
          const res = await fetch(`${API_URL}/api/intelligence/playbook`);
          if (!res.ok) throw new Error('Failed to fetch playbook data');
          setPlaybookData(await res.json());
          break;
        }
        case 'correlations': {
          const res = await fetch(`${API_URL}/api/intelligence/correlations`);
          if (!res.ok) throw new Error('Failed to fetch correlation data');
          setCorrelationData(await res.json());
          break;
        }
      }
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  // ──────────────────────────────────────────────
  // AI Analysis (Narrative) Functions
  // ──────────────────────────────────────────────

  const checkAiAvailability = async () => {
    try {
      const response = await fetch(`${API_URL}/api/narrative/status`);
      const data = await response.json();
      setAiAvailable(data.available);
    } catch (err) {
      console.error('Failed to check AI availability:', err);
      setAiAvailable(false);
    }
  };

  const fetchNarrativeModes = async () => {
    try {
      const response = await fetch(`${API_URL}/api/narrative/modes`);
      const data = await response.json();
      setNarrativeModes(data);
    } catch (err) {
      console.error('Failed to fetch narrative modes:', err);
    }
  };

  const generateNarrative = async () => {
    setNarrativeLoading(true);
    setNarrativeError(null);
    setShowModeSelector(false);

    try {
      const response = await fetch(`${API_URL}/api/narrative/generate?narrative_type=${selectedMode}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate narrative');
      }

      const data = await response.json();
      setNarrative(data);
    } catch (err) {
      setNarrativeError(err instanceof Error ? err.message : 'Failed to generate narrative');
    } finally {
      setNarrativeLoading(false);
    }
  };

  // ──────────────────────────────────────────────
  // Chat Functions
  // ──────────────────────────────────────────────

  const sendMessage = async (text?: string) => {
    const messageText = text || chatInput.trim();
    if (!messageText || chatLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/intelligence/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageText,
          session_id: sessionId,
          theory_depth: depthTier,
        }),
      });

      if (!res.ok) throw new Error('Chat request failed');

      const data = await res.json();

      if (data.session_id) setSessionId(data.session_id);
      if (data.tokens_used) setLastMetrics({ tokens: data.tokens_used, ms: data.elapsed_ms || 0 });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
        tokens_used: data.tokens_used,
        elapsed_ms: data.elapsed_ms,
        analytical_lens: data.analytical_lens,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setChatLoading(false);
    }
  };

  const resetChat = () => {
    setMessages([]);
    setSessionId(null);
    setLastMetrics(null);
    setExpandedLens(null);
  };

  const handleChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ──────────────────────────────────────────────
  // Helpers
  // ──────────────────────────────────────────────

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
      timeZone: 'America/New_York'
    }) + ' ET';
  };

  const tierColor = (tier: string) => {
    switch (tier) {
      case 'executive': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'analyst': return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
      case 'research': return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
      default: return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
    }
  };

  const tierDot = (tier: string) => {
    switch (tier) {
      case 'executive': return 'bg-amber-400';
      case 'analyst': return 'bg-blue-400';
      case 'research': return 'bg-purple-400';
      default: return 'bg-blue-400';
    }
  };

  const renderNarrative = (text: string) => {
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    return paragraphs.map((paragraph, idx) => (
      <p key={idx} className="mb-4 last:mb-0 leading-relaxed">
        {paragraph}
      </p>
    ));
  };

  // Dynamic content height
  const contentMinHeight = (activeTab === 'analysis' || activeTab === 'chat') ? 'min-h-[500px]' : 'min-h-[200px]';

  const tabs = [
    { id: 'regime' as TabId, label: 'Regime', icon: Activity },
    { id: 'playbook' as TabId, label: 'Playbook', icon: BookOpen },
    { id: 'correlations' as TabId, label: 'Correlations', icon: GitBranch },
    { id: 'analysis' as TabId, label: 'AI Analysis', icon: Brain },
    { id: 'chat' as TabId, label: 'Chat', icon: MessageCircle },
  ];

  return (
    <div className="bg-terminal-bg border border-terminal-border rounded-lg">
      {/* Header */}
      <div className="px-4 py-3 border-b border-terminal-border flex items-center justify-between">
        <h2 className="text-terminal-text font-mono text-sm font-semibold">
          MARKET INTELLIGENCE
        </h2>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-terminal-muted text-xs font-mono">
              {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          {regimeData && (
            <span className={`px-2 py-0.5 rounded text-xs font-bold text-white ${REGIME_COLORS[regimeData.regime] || 'bg-gray-500'}`}>
              {regimeData.regime.replace('_', ' ')}
            </span>
          )}
          <button
            onClick={fetchAllData}
            disabled={refreshing}
            className="p-1 rounded hover:bg-terminal-border text-terminal-muted hover:text-terminal-text transition-colors disabled:opacity-50"
            title="Refresh all intelligence data"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-terminal-border overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-mono transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'text-blue-400 border-b-2 border-blue-400 bg-blue-500/5'
                : 'text-terminal-text-dim hover:text-terminal-text'
            }`}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className={`${contentMinHeight}`}>
        {/* Regime / Playbook / Correlations tabs */}
        {(activeTab === 'regime' || activeTab === 'playbook' || activeTab === 'correlations') && (
          <div className="p-4">
            {loading && (
              <div className="flex items-center justify-center h-32">
                <div className="animate-pulse text-terminal-text-dim text-sm">Loading intelligence data...</div>
              </div>
            )}

            {error && (
              <div className="text-red-400 text-sm p-2 bg-red-500/10 rounded">
                {error}
                <button onClick={() => fetchTabData(activeTab as 'regime' | 'playbook' | 'correlations')} className="ml-2 underline">Retry</button>
              </div>
            )}

            {!loading && !error && activeTab === 'regime' && regimeData && (
              <RegimeView data={regimeData} />
            )}

            {!loading && !error && activeTab === 'playbook' && playbookData && (
              <PlaybookView data={playbookData} expandedMatch={expandedMatch} setExpandedMatch={setExpandedMatch} />
            )}

            {!loading && !error && activeTab === 'correlations' && correlationData && (
              <CorrelationsView data={correlationData} />
            )}
          </div>
        )}

        {/* AI Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="flex flex-col">
            {/* Analysis toolbar */}
            <div className="px-4 py-3 border-b border-terminal-border flex items-center justify-between gap-3">
              {/* Mode Selector */}
              {Object.keys(narrativeModes).length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowModeSelector(!showModeSelector)}
                    className="flex items-center gap-2 px-3 py-2 bg-terminal-dark border border-terminal-border rounded-lg hover:border-purple-500/50 transition-colors"
                  >
                    <span className="text-sm">
                      {narrativeModes[selectedMode]?.icon} {narrativeModes[selectedMode]?.name || 'Select Mode'}
                    </span>
                    <ChevronDown className={`w-4 h-4 transition-transform ${showModeSelector ? 'rotate-180' : ''}`} />
                  </button>

                  {showModeSelector && (
                    <div className="absolute left-0 mt-2 w-80 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                      {Object.entries(narrativeModes).map(([key, mode]) => (
                        <button
                          key={key}
                          onClick={() => {
                            setSelectedMode(key);
                            setShowModeSelector(false);
                          }}
                          className={`w-full text-left px-4 py-3 hover:bg-purple-500/10 transition-colors border-b border-terminal-border last:border-b-0 ${
                            selectedMode === key ? 'bg-purple-500/20' : ''
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <span className="text-lg">{mode.icon}</span>
                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-sm">{mode.name}</div>
                              <div className="text-xs text-terminal-text-dim mt-1">{mode.description}</div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={generateNarrative}
                disabled={narrativeLoading || aiAvailable === false}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  narrativeLoading
                    ? 'bg-purple-900/50 text-purple-300 cursor-wait'
                    : aiAvailable === false
                    ? 'bg-terminal-dark text-terminal-text-dim cursor-not-allowed'
                    : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-500/20'
                }`}
              >
                {narrativeLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Generate</span>
                  </>
                )}
              </button>
            </div>

            {/* Analysis content */}
            <div className="p-6 overflow-y-auto" style={{ maxHeight: '600px' }}>
              {aiAvailable === false && (
                <div className="flex items-center gap-3 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                  <div>
                    <p className="text-yellow-400 font-medium">AI Generation Unavailable</p>
                    <p className="text-sm text-terminal-text-dim mt-1">
                      Configure ANTHROPIC_API_KEY in your .env file to enable AI-powered analysis.
                    </p>
                  </div>
                </div>
              )}

              {narrativeError && (
                <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                  <div>
                    <p className="text-red-400 font-medium">Generation Failed</p>
                    <p className="text-sm text-terminal-text-dim mt-1">{narrativeError}</p>
                  </div>
                </div>
              )}

              {narrativeLoading && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 text-purple-400">
                    <div className="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                    <span>Analyzing market data and generating narrative...</span>
                  </div>
                  <div className="space-y-3">
                    {[1, 2, 3, 4, 5, 6].map(i => (
                      <div key={i} className={`h-4 bg-terminal-dark rounded animate-pulse`} style={{ width: `${85 + Math.random() * 15}%` }} />
                    ))}
                  </div>
                </div>
              )}

              {!narrativeLoading && !narrative && aiAvailable !== false && (
                <div className="text-center py-12">
                  <Brain className="w-16 h-16 text-terminal-text-dim mx-auto mb-4 opacity-30" />
                  <p className="text-terminal-text-dim text-lg mb-2">No analysis generated yet</p>
                  <p className="text-terminal-text-dim text-sm">
                    Select an analyst mode and click "Generate" to create an AI-powered narrative.
                  </p>
                </div>
              )}

              {!narrativeLoading && narrative && (
                <div>
                  <div className="prose prose-invert max-w-none text-terminal-text">
                    {renderNarrative(narrative.narrative)}
                  </div>

                  {/* Footer metadata */}
                  <div className="mt-6 pt-4 border-t border-terminal-border flex items-center justify-between text-xs text-terminal-text-dim flex-wrap gap-3">
                    <div className="flex items-center gap-4 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTimestamp(narrative.generated_at)}
                      </span>
                      {narrative.narrative_mode && (
                        <>
                          <span>|</span>
                          <span className="flex items-center gap-1">
                            <span>{narrativeModes[narrative.narrative_type || '']?.icon || '📊'}</span>
                            <span>{narrative.narrative_mode}</span>
                          </span>
                        </>
                      )}
                      {narrative.market_regime && (
                        <>
                          <span>|</span>
                          <span>Regime: {narrative.market_regime}</span>
                        </>
                      )}
                      <span>|</span>
                      <span>{narrative.indicators_count} indicators</span>
                      <span>|</span>
                      <span>{narrative.news_count} news items</span>
                      {narrative.data_quality && (
                        <>
                          <span>|</span>
                          <span className={`px-2 py-0.5 rounded ${
                            narrative.data_quality.quality_level === 'EXCELLENT' ? 'bg-green-500/20 text-green-400' :
                            narrative.data_quality.quality_level === 'GOOD' ? 'bg-blue-500/20 text-blue-400' :
                            narrative.data_quality.quality_level === 'FAIR' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-red-500/20 text-red-400'
                          }`}>
                            Data: {narrative.data_quality.quality_score}/100
                          </span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {narrative.is_fallback ? (
                        <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                          Template Mode
                        </span>
                      ) : (
                        <>
                          <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                            Claude Sonnet 4.5
                          </span>
                          {narrative.from_cache && (
                            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                              Cached ({narrative.cache_age_minutes}m)
                            </span>
                          )}
                          <span>{narrative.tokens_used.toLocaleString()} tokens</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Analytical Lens */}
                  {narrative.analytical_lens && narrative.analytical_lens.theory_count > 0 && (
                    <div className="mt-4 pt-4 border-t border-terminal-border">
                      <button
                        onClick={() => setShowAnalyticalLens(!showAnalyticalLens)}
                        className="flex items-center gap-2 text-xs text-terminal-text-dim hover:text-terminal-text transition-colors"
                      >
                        <ChevronDown className={`w-3 h-3 transition-transform ${showAnalyticalLens ? 'rotate-180' : ''}`} />
                        <BookOpenCheck className="w-3 h-3" />
                        <span>
                          Analytical Lens: {narrative.analytical_lens.tier_name} · {narrative.analytical_lens.theory_count} frameworks applied
                        </span>
                      </button>
                      {showAnalyticalLens && (
                        <div className="mt-3 p-4 bg-terminal-dark rounded-lg border border-terminal-border">
                          <div className="text-xs space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-terminal-text-dim">Depth Tier:</span>
                              <span className={`font-bold px-2 py-0.5 rounded ${
                                narrative.analytical_lens.depth_tier === 'executive' ? 'bg-amber-500/20 text-amber-400' :
                                narrative.analytical_lens.depth_tier === 'analyst' ? 'bg-blue-500/20 text-blue-400' :
                                'bg-purple-500/20 text-purple-400'
                              }`}>
                                {narrative.analytical_lens.tier_name}
                              </span>
                            </div>
                            <div>
                              <span className="text-terminal-text-dim">{narrative.analytical_lens.tier_description}</span>
                            </div>
                            <div className="pt-2 border-t border-terminal-border">
                              <span className="text-terminal-text-dim font-medium">Frameworks Applied:</span>
                              <div className="mt-2 space-y-1.5">
                                {narrative.analytical_lens.theories_applied.map((theory, idx) => (
                                  <div key={idx} className="flex items-center gap-2">
                                    <span className={`w-1.5 h-1.5 rounded-full ${tierDot(narrative.analytical_lens!.depth_tier)}`} />
                                    <span className="text-terminal-text">{theory.name}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Data Quality */}
                  {narrative.data_quality && (
                    <div className="mt-4 pt-4 border-t border-terminal-border">
                      <button
                        onClick={() => setShowDataQuality(!showDataQuality)}
                        className="flex items-center gap-2 text-xs text-terminal-text-dim hover:text-terminal-text transition-colors"
                      >
                        <ChevronDown className={`w-3 h-3 transition-transform ${showDataQuality ? 'rotate-180' : ''}`} />
                        <span>View Data Quality Details</span>
                      </button>
                      {showDataQuality && (
                        <div className="mt-3 p-4 bg-terminal-dark rounded-lg border border-terminal-border">
                          <div className="text-xs space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-terminal-text-dim">Overall Quality:</span>
                              <span className={`font-bold ${
                                narrative.data_quality.quality_level === 'EXCELLENT' ? 'text-green-400' :
                                narrative.data_quality.quality_level === 'GOOD' ? 'text-blue-400' :
                                narrative.data_quality.quality_level === 'FAIR' ? 'text-yellow-400' :
                                'text-red-400'
                              }`}>
                                {narrative.data_quality.quality_level} ({narrative.data_quality.quality_score}/100)
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-terminal-text-dim">Indicators:</span>
                              <span>{narrative.data_quality.indicators_available} / {narrative.data_quality.indicators_expected}</span>
                            </div>
                            {narrative.data_quality.missing_critical.length > 0 && (
                              <div>
                                <span className="text-red-400 font-medium">Missing Critical:</span>
                                <ul className="mt-1 ml-4 list-disc text-terminal-text-dim">
                                  {narrative.data_quality.missing_critical.map((item, idx) => (
                                    <li key={idx}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Context Snapshot */}
                  {narrative.context_snapshot && (
                    <div className="mt-4 pt-4 border-t border-terminal-border">
                      <button
                        onClick={() => setShowContextSnapshot(!showContextSnapshot)}
                        className="flex items-center gap-2 text-xs text-terminal-text-dim hover:text-terminal-text transition-colors"
                      >
                        <ChevronDown className={`w-3 h-3 transition-transform ${showContextSnapshot ? 'rotate-180' : ''}`} />
                        <span>View Context Snapshot (Audit Trail)</span>
                      </button>
                      {showContextSnapshot && (
                        <div className="mt-3 p-4 bg-terminal-dark rounded-lg border border-terminal-border overflow-x-auto">
                          <pre className="text-xs text-terminal-text-dim font-mono whitespace-pre-wrap">
                            {narrative.context_snapshot}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="flex flex-col" style={{ height: '500px' }}>
            {/* Chat toolbar */}
            <div className="px-4 py-2 border-b border-terminal-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Depth Tier Selector */}
                <div className="relative" ref={tierSelectorRef}>
                  <button
                    onClick={() => setShowTierSelector(!showTierSelector)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono border transition-colors ${tierColor(depthTier)}`}
                    title="Analytical depth tier"
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${tierDot(depthTier)}`} />
                    {DEPTH_TIERS[depthTier]?.name || 'Analyst'}
                    <ChevronDown size={10} className={`transition-transform ${showTierSelector ? 'rotate-180' : ''}`} />
                  </button>

                  {showTierSelector && (
                    <div className="absolute left-0 mt-1 w-56 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50">
                      {Object.entries(DEPTH_TIERS).map(([key, tier]) => (
                        <button
                          key={key}
                          onClick={() => {
                            setDepthTier(key);
                            setShowTierSelector(false);
                          }}
                          className={`w-full text-left px-3 py-2 hover:bg-terminal-border/50 transition-colors first:rounded-t-lg last:rounded-b-lg ${
                            depthTier === key ? 'bg-terminal-border/30' : ''
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${tierDot(key)}`} />
                            <div>
                              <div className="text-xs font-medium text-terminal-text">{tier.name}</div>
                              <div className="text-[10px] text-terminal-text-dim">{tier.description}</div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {messages.length > 0 && (
                  <span className="text-[10px] text-terminal-text-dim font-mono">
                    {messages.filter(m => m.role === 'user').length} turns
                    {lastMetrics && ` · ${lastMetrics.tokens} tokens`}
                  </span>
                )}
              </div>

              <button
                onClick={resetChat}
                className="flex items-center gap-1 px-2 py-1 hover:bg-terminal-border rounded text-terminal-text-dim hover:text-terminal-text transition-colors text-xs"
                title="Reset conversation"
              >
                <RotateCcw size={12} />
                <span>Reset</span>
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <div className="space-y-4">
                  <p className="text-terminal-text-dim text-sm text-center mt-6">
                    Ask me about markets, economics, or any data in the terminal.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl mx-auto">
                    {EXAMPLE_QUESTIONS.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => sendMessage(q)}
                        className="text-left px-3 py-2 text-xs text-blue-400 bg-blue-500/5 hover:bg-blue-500/10 border border-blue-500/20 rounded transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-terminal-border text-terminal-text'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>

                    {/* Analytical Lens Badge */}
                    {msg.role === 'assistant' && msg.analytical_lens && (
                      <div className="mt-2">
                        <button
                          onClick={() => setExpandedLens(expandedLens === i ? null : i)}
                          className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono border transition-colors ${tierColor(msg.analytical_lens.depth_tier)}`}
                        >
                          <BookOpenCheck size={8} />
                          {msg.analytical_lens.tier_name} · {msg.analytical_lens.theory_count} frameworks
                        </button>

                        {expandedLens === i && (
                          <div className="mt-1.5 p-2 bg-terminal-bg/50 rounded border border-terminal-border/50 text-[10px]">
                            <div className="text-terminal-text-dim mb-1 font-semibold">Analytical Lens</div>
                            <div className="space-y-0.5">
                              {msg.analytical_lens.theories_applied.map((theory, j) => (
                                <div key={j} className="flex items-center gap-1 text-terminal-text-dim">
                                  <span className="text-[8px]">▸</span>
                                  <span>{theory.name}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {msg.role === 'assistant' && msg.elapsed_ms && (
                      <div className="flex items-center gap-2 mt-1.5 pt-1 border-t border-terminal-border/50 text-[10px] text-terminal-text-dim">
                        <span className="flex items-center gap-0.5">
                          <Clock size={8} /> {(msg.elapsed_ms / 1000).toFixed(1)}s
                        </span>
                        {msg.tokens_used && (
                          <span className="flex items-center gap-0.5">
                            <Zap size={8} /> {msg.tokens_used} tokens
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-terminal-border px-3 py-2 rounded-lg">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Chat input */}
            <div className="p-3 border-t border-terminal-border">
              <div className="flex items-center gap-2">
                <input
                  ref={chatInputRef}
                  type="text"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={handleChatKeyDown}
                  placeholder="Ask about markets, economics, indicators..."
                  disabled={chatLoading}
                  className="flex-1 bg-terminal-border text-terminal-text text-sm px-3 py-2 rounded font-mono placeholder-terminal-text-dim focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={chatLoading || !chatInput.trim()}
                  className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-terminal-border disabled:text-terminal-text-dim text-white rounded transition-colors"
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────
// Regime Tab
// ──────────────────────────────────────────────

const RegimeView: React.FC<{ data: RegimeData }> = ({ data }) => (
  <div className="space-y-4">
    <div className="flex items-center gap-3">
      <div className={`w-3 h-3 rounded-full ${REGIME_COLORS[data.regime] || 'bg-gray-500'}`} />
      <div>
        <span className={`font-mono font-bold text-sm ${REGIME_TEXT_COLORS[data.regime] || 'text-gray-400'}`}>
          {data.regime.replace('_', ' ')}
        </span>
        <p className="text-terminal-text-dim text-xs mt-0.5">{data.regime_description}</p>
      </div>
    </div>

    {(data.critical_count > 0 || data.high_count > 0) && (
      <div className="flex gap-3 text-xs">
        {data.critical_count > 0 && (
          <span className="flex items-center gap-1 text-red-400">
            <AlertTriangle size={12} /> {data.critical_count} Critical
          </span>
        )}
        {data.high_count > 0 && (
          <span className="flex items-center gap-1 text-orange-400">
            <AlertTriangle size={12} /> {data.high_count} High
          </span>
        )}
      </div>
    )}

    {data.shifts.length > 0 ? (
      <div className="space-y-2">
        <h3 className="text-terminal-text text-xs font-mono font-semibold">ACTIVE SHIFTS</h3>
        {data.shifts.map((shift, i) => (
          <div key={i} className={`border-l-2 pl-3 py-2 ${SEVERITY_COLORS[shift.severity] || ''}`}>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold">{shift.signal_name}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-terminal-border">{shift.severity}</span>
            </div>
            <p className="text-xs mt-1 text-terminal-text-dim">{shift.description}</p>
            {shift.ai_explanation && (
              <p className="text-xs mt-1.5 text-blue-300/80 italic">{shift.ai_explanation}</p>
            )}
          </div>
        ))}
      </div>
    ) : (
      <p className="text-terminal-text-dim text-xs">No active regime shifts detected.</p>
    )}
  </div>
);

// ──────────────────────────────────────────────
// Playbook Tab
// ──────────────────────────────────────────────

const PlaybookView: React.FC<{
  data: PlaybookData;
  expandedMatch: string | null;
  setExpandedMatch: (id: string | null) => void;
}> = ({ data, expandedMatch, setExpandedMatch }) => (
  <div className="space-y-3">
    <h3 className="text-terminal-text text-xs font-mono font-semibold">HISTORICAL PARALLELS</h3>

    {data.matches.map(match => (
      <div
        key={match.episode_id}
        className="border border-terminal-border rounded p-3 cursor-pointer hover:border-blue-500/50 transition-colors"
        onClick={() => setExpandedMatch(expandedMatch === match.episode_id ? null : match.episode_id)}
      >
        <div className="flex items-center justify-between">
          <span className="text-terminal-text text-xs font-mono font-semibold">{match.episode_name}</span>
          <span className="text-xs font-mono text-terminal-text-dim">{match.period}</span>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-terminal-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                match.similarity_pct >= 70 ? 'bg-red-500' :
                match.similarity_pct >= 50 ? 'bg-orange-500' :
                match.similarity_pct >= 30 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${match.similarity_pct}%` }}
            />
          </div>
          <span className="text-xs font-mono font-bold text-terminal-text w-10 text-right">
            {match.similarity_pct}%
          </span>
        </div>

        <div className="text-[10px] text-terminal-text-dim mt-1">
          {match.matching_count}/{match.total_signals} signals match
        </div>

        {expandedMatch === match.episode_id && (
          <div className="mt-3 pt-3 border-t border-terminal-border space-y-2">
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <span className="text-green-400 font-semibold">MATCHING:</span>
                <div className="text-terminal-text-dim mt-0.5">
                  {match.matching_signals.map(s => s.replace(/_/g, ' ')).join(', ')}
                </div>
              </div>
              <div>
                <span className="text-red-400 font-semibold">DIVERGING:</span>
                <div className="text-terminal-text-dim mt-0.5">
                  {match.diverging_signals.map(s => s.replace(/_/g, ' ')).join(', ')}
                </div>
              </div>
            </div>
            <div>
              <span className="text-blue-400 text-[10px] font-semibold">WHAT FOLLOWED:</span>
              <p className="text-terminal-text-dim text-xs mt-0.5">{match.what_followed}</p>
            </div>
          </div>
        )}
      </div>
    ))}

    {data.ai_analysis && (
      <div className="mt-3 p-3 bg-blue-500/5 border border-blue-500/20 rounded">
        <span className="text-blue-400 text-[10px] font-semibold">AI ANALYSIS</span>
        <p className="text-terminal-text text-xs mt-1">{data.ai_analysis}</p>
      </div>
    )}
  </div>
);

// ──────────────────────────────────────────────
// Correlations Tab
// ──────────────────────────────────────────────

const CorrelationsView: React.FC<{ data: CorrelationData }> = ({ data }) => (
  <div className="space-y-3">
    {data.breakdowns_detected > 0 && (
      <div className="flex items-center gap-2 text-xs text-orange-400 bg-orange-500/10 p-2 rounded">
        <AlertTriangle size={14} />
        {data.breakdowns_detected} correlation breakdown{data.breakdowns_detected > 1 ? 's' : ''} detected
      </div>
    )}

    <div className="space-y-2">
      {data.pairs.map(pair => (
        <div
          key={pair.id}
          className={`border rounded p-3 ${
            pair.breakdown_detected
              ? 'border-orange-500/50 bg-orange-500/5'
              : pair.status === 'warning'
              ? 'border-yellow-500/30 bg-yellow-500/5'
              : 'border-terminal-border'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-terminal-text text-xs font-mono font-semibold">{pair.name}</span>
            {pair.breakdown_detected && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-bold">
                BREAKDOWN
              </span>
            )}
          </div>

          {pair.error ? (
            <p className="text-red-400 text-[10px] mt-1">{pair.error}</p>
          ) : (
            <>
              <div className="flex items-center gap-4 mt-2 text-xs">
                <div>
                  <span className="text-terminal-text-dim">30d: </span>
                  <CorrelationValue value={pair.corr_30d} normalRange={pair.normal_range} />
                </div>
                <div>
                  <span className="text-terminal-text-dim">90d: </span>
                  <CorrelationValue value={pair.corr_90d} normalRange={pair.normal_range} />
                </div>
                <div className="text-terminal-text-dim text-[10px]">
                  Normal: [{pair.normal_range[0]}, {pair.normal_range[1]}]
                </div>
              </div>
              <p className="text-terminal-text-dim text-[10px] mt-1.5">
                {pair.breakdown_detected ? pair.breakdown_meaning : pair.description}
              </p>
            </>
          )}
        </div>
      ))}
    </div>
  </div>
);

const CorrelationValue: React.FC<{ value: number | null; normalRange: number[] }> = ({ value, normalRange }) => {
  if (value === null) return <span className="text-terminal-text-dim font-mono">N/A</span>;

  const isNormal = value >= normalRange[0] && value <= normalRange[1];
  const Icon = value > 0 ? TrendingUp : value < 0 ? TrendingDown : Minus;

  return (
    <span className={`font-mono font-bold ${isNormal ? 'text-terminal-text' : 'text-orange-400'}`}>
      <Icon size={10} className="inline mr-0.5" />
      {value.toFixed(3)}
    </span>
  );
};
