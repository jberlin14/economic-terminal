import React, { useState, useMemo } from 'react';
import { ExternalLink, Clock } from 'lucide-react';

const CATEGORY_TABS = [
  { key: 'ALL', label: 'ALL' },
  { key: 'CENTRAL_BANK', label: 'CENTRAL BANK' },
  { key: 'GEOPOLITICAL', label: 'GEOPOLITICAL' },
  { key: 'TRADE_POLICY', label: 'TRADE' },
  { key: 'ECON', label: 'ECON' },
  { key: 'POLITICAL', label: 'POLITICAL' },
  { key: 'FX', label: 'FX' },
  { key: 'CREDIT', label: 'CREDIT' },
] as const;

const SEVERITY_TABS = [
  { key: 'ALL', label: 'ALL', activeClass: 'bg-neutral text-white', inactiveClass: 'border-neutral/40 text-neutral' },
  { key: 'CRITICAL', label: 'CRITICAL', activeClass: 'bg-critical text-white', inactiveClass: 'border-critical/40 text-critical' },
  { key: 'HIGH', label: 'HIGH', activeClass: 'bg-warning text-black', inactiveClass: 'border-warning/40 text-warning' },
  { key: 'MEDIUM', label: 'MEDIUM', activeClass: 'bg-neutral text-white', inactiveClass: 'border-neutral/40 text-neutral' },
] as const;

const CATEGORY_DISPLAY: Record<string, string> = {
  ECON: 'ECON',
  FX: 'FX',
  POLITICAL: 'POLITICAL',
  CREDIT: 'CREDIT',
  CENTRAL_BANK: 'CENTRAL BANK',
  GEOPOLITICAL: 'GEOPOLITICAL',
  TRADE_POLICY: 'TRADE',
  CURRENCY: 'FX',
  CAT: 'CRITICAL',
};

const SOURCE_DISPLAY: Record<string, string> = {
  bloomberg: 'Bloomberg',
  cnbc: 'CNBC',
  yahoo: 'Yahoo Finance',
  ft_markets: 'Financial Times',
  marketwatch: 'MarketWatch',
  the_hill: 'The Hill',
  politico: 'Politico',
  foreign_policy: 'Foreign Policy',
  foreign_affairs: 'Foreign Affairs',
  defense_news: 'Defense News',
  war_on_rocks: 'War on the Rocks',
  brookings: 'Brookings',
  fed: 'Federal Reserve',
  ecb: 'ECB',
  boe: 'Bank of England',
  boj: 'Bank of Japan',
  boc: 'Bank of Canada',
  rba: 'RBA',
  rbnz: 'RBNZ',
  ap_politics: 'AP News',
  treasury_gov: 'US Treasury',
  white_house: 'White House',
  ustr: 'USTR',
  cbo: 'CBO',
  imf: 'IMF',
};

interface NewsArticle {
  id: number;
  headline: string;
  source: string;
  url?: string;
  published_at: string;
  country_tags: string[];
  category: string;
  severity: string;
  leader_mentions?: string[];
  institutions?: string[];
  event_types?: string[];
  action_words?: string[];
}

interface NewsFeedProps {
  articles: NewsArticle[];
}

export const NewsFeed: React.FC<NewsFeedProps> = ({ articles }) => {
  const [activeCategory, setActiveCategory] = useState<string>('ALL');
  const [activeSeverity, setActiveSeverity] = useState<string>('ALL');

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const a of articles) {
      counts[a.category] = (counts[a.category] || 0) + 1;
    }
    return counts;
  }, [articles]);

  const filteredArticles = useMemo(() => {
    return articles.filter((a) => {
      if (activeCategory !== 'ALL' && a.category !== activeCategory) return false;
      if (activeSeverity !== 'ALL' && a.severity !== activeSeverity) return false;
      return true;
    });
  }, [articles, activeCategory, activeSeverity]);

  const isFiltered = activeCategory !== 'ALL' || activeSeverity !== 'ALL';

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-critical text-white';
      case 'HIGH':
        return 'bg-warning text-black';
      case 'MEDIUM':
        return 'bg-neutral text-white';
      default:
        return 'bg-terminal-border text-terminal-text-dim';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'ECON': return 'text-chart-blue';
      case 'FX': return 'text-chart-purple';
      case 'POLITICAL': return 'text-chart-pink';
      case 'CREDIT': return 'text-chart-cyan';
      case 'CENTRAL_BANK': return 'text-chart-blue';
      case 'GEOPOLITICAL': return 'text-critical';
      case 'TRADE_POLICY': return 'text-warning';
      case 'CURRENCY': return 'text-chart-purple';
      case 'CAT': return 'text-critical';
      default: return 'text-terminal-text-dim';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      return 'Unknown';
    }
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const absDiffMs = Math.abs(diffMs);
    const diffMins = Math.floor(absDiffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMs < 0) {
      // Future date (timezone mismatch) - just show the date
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } else if (diffMins < 1) {
      return 'Just now';
    } else if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  };

  if (articles.length === 0) {
    return (
      <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
        <h2 className="text-xl font-bold mb-4">News Feed</h2>
        <div className="text-terminal-text-dim text-center py-8">
          No recent news articles
        </div>
      </div>
    );
  }

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>News Feed</span>
        <span className="text-sm font-normal text-terminal-text-dim ml-auto">
          {isFiltered ? `${filteredArticles.length} of ${articles.length}` : articles.length} articles &middot; Last 24 hours
        </span>
      </h2>

      {/* Category Filter Tabs */}
      <div className="flex gap-1.5 mb-2 overflow-x-auto pb-1">
        {CATEGORY_TABS.map((tab) => {
          const count = tab.key === 'ALL' ? articles.length : (categoryCounts[tab.key] || 0);
          return (
            <button
              key={tab.key}
              onClick={() => setActiveCategory(tab.key)}
              className={`px-2.5 py-1 rounded text-xs font-mono whitespace-nowrap transition-colors ${
                activeCategory === tab.key
                  ? 'bg-neutral text-white'
                  : 'bg-terminal-border text-terminal-text-dim hover:text-terminal-text'
              }`}
            >
              {tab.label}
              <span className={`ml-1 ${activeCategory === tab.key ? 'text-white/60' : 'text-terminal-text-dim/60'}`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Severity Filter */}
      <div className="flex gap-1.5 mb-3">
        {SEVERITY_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSeverity(tab.key)}
            className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
              activeSeverity === tab.key
                ? tab.activeClass
                : `border ${tab.inactiveClass} bg-transparent hover:bg-terminal-border`
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {filteredArticles.length === 0 && isFiltered && (
          <div className="text-center py-8">
            <p className="text-terminal-text-dim text-sm mb-2">No articles match current filters</p>
            <button
              onClick={() => { setActiveCategory('ALL'); setActiveSeverity('ALL'); }}
              className="text-xs text-neutral hover:text-chart-blue transition-colors font-mono"
            >
              Clear filters
            </button>
          </div>
        )}
        {filteredArticles.map((article) => (
          <div
            key={article.id}
            className="p-3 rounded-lg bg-terminal-dark border border-terminal-border hover:border-neutral transition-colors"
          >
            <div className="flex items-start gap-3">
              <div className="flex-grow min-w-0">
                {/* Header */}
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {/* Severity Badge */}
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${getSeverityBadge(article.severity)}`}>
                    {article.severity}
                  </span>

                  {/* Category */}
                  <span className={`text-xs font-mono ${getCategoryColor(article.category)}`}>
                    {CATEGORY_DISPLAY[article.category] || article.category}
                  </span>

                  {/* Source */}
                  <span className="text-xs text-terminal-text-dim">
                    {SOURCE_DISPLAY[article.source] || article.source}
                  </span>

                  {/* Time */}
                  <span className="text-xs text-terminal-text-dim flex items-center gap-1 ml-auto">
                    <Clock className="w-3 h-3" />
                    {formatTime(article.published_at)}
                  </span>
                </div>

                {/* Headline */}
                <div className="font-medium text-sm leading-tight">
                  {article.headline}
                </div>

                {/* Country Tags */}
                {article.country_tags && article.country_tags.length > 0 && (
                  <div className="flex gap-1 mt-2">
                    {article.country_tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-1.5 py-0.5 bg-terminal-border rounded text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Leader Mentions, Institutions, and Events */}
                {((article.leader_mentions && article.leader_mentions.length > 0) ||
                  (article.institutions && article.institutions.length > 0) ||
                  (article.event_types && article.event_types.length > 0)) && (
                  <div className="flex gap-2 mt-2 flex-wrap text-xs">
                    {/* Leader Mentions */}
                    {article.leader_mentions && article.leader_mentions.length > 0 && (
                      <div className="flex gap-1 items-center">
                        <span className="text-terminal-text-dim">👤</span>
                        {article.leader_mentions.slice(0, 3).map((leader) => (
                          <span
                            key={leader}
                            className="px-1.5 py-0.5 bg-chart-purple/20 text-chart-purple rounded text-xs"
                          >
                            {leader.toUpperCase()}
                          </span>
                        ))}
                        {article.leader_mentions.length > 3 && (
                          <span className="text-terminal-text-dim">+{article.leader_mentions.length - 3}</span>
                        )}
                      </div>
                    )}

                    {/* Institutions */}
                    {article.institutions && article.institutions.length > 0 && (
                      <div className="flex gap-1 items-center">
                        <span className="text-terminal-text-dim">🏛️</span>
                        {article.institutions.slice(0, 2).map((inst) => (
                          <span
                            key={inst}
                            className="px-1.5 py-0.5 bg-chart-blue/20 text-chart-blue rounded text-xs"
                          >
                            {inst}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Event Types */}
                    {article.event_types && article.event_types.length > 0 && (
                      <div className="flex gap-1 items-center">
                        <span className="text-terminal-text-dim">📌</span>
                        {article.event_types.slice(0, 2).map((event) => (
                          <span
                            key={event}
                            className="px-1.5 py-0.5 bg-chart-cyan/20 text-chart-cyan rounded text-xs"
                          >
                            {event.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* External Link */}
              {article.url && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-terminal-text-dim hover:text-neutral flex-shrink-0"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
