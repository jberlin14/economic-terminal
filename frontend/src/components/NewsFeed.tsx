import React from 'react';
import { ExternalLink, Clock } from 'lucide-react';

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
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    
    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  };

  if (articles.length === 0) {
    return (
      <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
        <h2 className="text-xl font-bold mb-4">📰 News Feed</h2>
        <div className="text-terminal-text-dim text-center py-8">
          No recent news articles
        </div>
      </div>
    );
  }

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>📰</span>
        <span>News Feed</span>
        <span className="text-sm font-normal text-terminal-text-dim ml-auto">
          Last 24 hours
        </span>
      </h2>
      
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {articles.map((article) => (
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
                    {article.category}
                  </span>
                  
                  {/* Source */}
                  <span className="text-xs text-terminal-text-dim">
                    {article.source}
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
