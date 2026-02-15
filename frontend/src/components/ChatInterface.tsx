import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, RotateCcw, Clock, Zap, BookOpen, ChevronDown } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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

export const ChatInterface: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lastMetrics, setLastMetrics] = useState<{ tokens: number; ms: number } | null>(null);
  const [depthTier, setDepthTier] = useState<string>('analyst');
  const [showTierSelector, setShowTierSelector] = useState(false);
  const [expandedLens, setExpandedLens] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const tierSelectorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  // Close tier selector when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (tierSelectorRef.current && !tierSelectorRef.current.contains(e.target as Node)) {
        setShowTierSelector(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const sendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || loading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

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
      setLoading(false);
    }
  };

  const resetChat = () => {
    setMessages([]);
    setSessionId(null);
    setLastMetrics(null);
    setExpandedLens(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
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

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 z-50"
        title="Open AI Chat"
      >
        <MessageCircle size={24} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[36rem] bg-terminal-bg border border-terminal-border rounded-lg shadow-2xl flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <MessageCircle size={16} className="text-blue-400" />
          <span className="text-terminal-text font-mono text-sm font-semibold">AI ANALYST</span>
        </div>
        <div className="flex items-center gap-1">
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
              <div className="absolute right-0 mt-1 w-56 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50">
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

          <button
            onClick={resetChat}
            className="p-1.5 hover:bg-terminal-border rounded text-terminal-text-dim hover:text-terminal-text transition-colors"
            title="Reset conversation"
          >
            <RotateCcw size={14} />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 hover:bg-terminal-border rounded text-terminal-text-dim hover:text-terminal-text transition-colors"
            title="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-terminal-text-dim text-xs text-center mt-4">
              Ask me about markets, economics, or any data in the terminal.
            </p>
            <div className="space-y-1.5">
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(q)}
                  className="w-full text-left px-3 py-2 text-xs text-blue-400 bg-blue-500/5 hover:bg-blue-500/10 border border-blue-500/20 rounded transition-colors"
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
              className={`max-w-[85%] px-3 py-2 rounded-lg text-xs ${
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
                    <BookOpen size={8} />
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

        {loading && (
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

      {/* Metrics Bar */}
      {lastMetrics && (
        <div className="px-3 py-1 border-t border-terminal-border/50 flex items-center gap-3 text-[10px] text-terminal-text-dim">
          <span>Session: {messages.filter(m => m.role === 'user').length} turns</span>
          <span>Last: {lastMetrics.tokens} tokens, {(lastMetrics.ms / 1000).toFixed(1)}s</span>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-terminal-border">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about markets..."
            disabled={loading}
            className="flex-1 bg-terminal-border text-terminal-text text-xs px-3 py-2 rounded font-mono placeholder-terminal-text-dim focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-terminal-border disabled:text-terminal-text-dim text-white rounded transition-colors"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};
