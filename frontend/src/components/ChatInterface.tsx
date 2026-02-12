import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Loader2, RotateCcw } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  tokens_used?: number;
  elapsed_ms?: number;
}

const EXAMPLE_QUESTIONS = [
  "Why did the 2s10s spread widen today?",
  "Compare current labor market to 2019",
  "What would a 50bp cut mean for equities?",
  "What's driving the VIX right now?",
  "Is the yield curve signaling recession?",
  "Summarize today's market conditions",
];

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const sendMessage = async (question?: string) => {
    const q = question || input.trim();
    if (!q || loading) return;

    const userMessage: ChatMessage = { role: 'user', content: q };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/intelligence/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();

      if (data.session_id) {
        setSessionId(data.session_id);
      }

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.response,
        timestamp: data.timestamp,
        tokens_used: data.tokens_used,
        elapsed_ms: data.elapsed_ms,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg shadow-blue-500/30 transition-all hover:scale-105"
      >
        <MessageSquare className="w-5 h-5" />
        <span className="font-medium">Ask AI</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[420px] max-h-[600px] flex flex-col bg-terminal-panel border border-terminal-border rounded-xl shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-900/40 to-transparent border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-400" />
          <span className="font-bold text-sm">Market Intelligence Chat</span>
          {sessionId && (
            <span className="text-[10px] text-terminal-text-dim px-1.5 py-0.5 bg-terminal-dark rounded">
              Session: {sessionId}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={resetChat}
            className="p-1.5 hover:bg-terminal-dark rounded transition-colors"
            title="New conversation"
          >
            <RotateCcw className="w-3.5 h-3.5 text-terminal-text-dim" />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="text-terminal-text-dim hover:text-terminal-text text-lg leading-none px-1"
          >
            &times;
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px] max-h-[420px]">
        {messages.length === 0 && (
          <div className="text-center py-6">
            <MessageSquare className="w-10 h-10 text-terminal-text-dim mx-auto mb-3 opacity-30" />
            <p className="text-terminal-text-dim text-sm mb-4">
              Ask questions about the economy and markets
            </p>
            <div className="space-y-2">
              {EXAMPLE_QUESTIONS.slice(0, 4).map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => sendMessage(q)}
                  className="block w-full text-left text-xs px-3 py-2 bg-terminal-dark border border-terminal-border rounded-lg hover:border-blue-500/50 hover:bg-blue-500/5 transition-colors text-terminal-text-dim"
                >
                  "{q}"
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] px-3 py-2 rounded-lg text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600/20 border border-blue-500/30 text-terminal-text'
                  : 'bg-terminal-dark border border-terminal-border text-terminal-text'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.role === 'assistant' && msg.elapsed_ms && (
                <div className="mt-2 text-[10px] text-terminal-text-dim flex items-center gap-2">
                  <span>{msg.elapsed_ms}ms</span>
                  {msg.tokens_used && <span>{msg.tokens_used} tokens</span>}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="px-3 py-2 bg-terminal-dark border border-terminal-border rounded-lg">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-terminal-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the economy..."
            className="flex-1 px-3 py-2 bg-terminal-dark border border-terminal-border rounded-lg text-sm text-terminal-text placeholder-terminal-text-dim focus:outline-none focus:border-blue-500/50"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-terminal-dark disabled:text-terminal-text-dim text-white rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
