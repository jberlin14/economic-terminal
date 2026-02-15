import React, { useEffect, useState } from 'react';
import { Calendar as CalendarIcon, Clock, TrendingUp, TrendingDown, AlertCircle, ChevronRight, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Release {
  id: string;
  name: string;
  series_id: string;
  importance: 'high' | 'medium' | 'low';
  typical_time: string;
  frequency: string;
  description: string;
  release_date: string | null;
  previous_value: number | null;
  previous_date: string | null;
  consensus_estimate: number | null;
  actual_value: number | null;
  surprise: number | null;
  surprise_percent: number | null;
}

interface CalendarData {
  timestamp: string;
  total_upcoming: number;
  high_importance_count: number;
  this_week: Release[];
  next_week: Release[];
  all_upcoming: Release[];
}

interface ReleaseHistory {
  date: string;
  value: number | null;
  change: number | null;
  change_percent: number | null;
}

interface ReleaseDetail {
  release: Release;
  next_release: Release | null;
  history: ReleaseHistory[];
}

export const Calendar: React.FC = () => {
  const [calendarData, setCalendarData] = useState<CalendarData | null>(null);
  const [selectedRelease, setSelectedRelease] = useState<string | null>(null);
  const [releaseDetail, setReleaseDetail] = useState<ReleaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCalendar();
  }, []);

  useEffect(() => {
    if (selectedRelease) {
      fetchReleaseDetail(selectedRelease);
    }
  }, [selectedRelease]);

  const fetchCalendar = async () => {
    try {
      setRefreshing(true);
      const response = await fetch(`${API_URL}/api/calendar/`);
      if (!response.ok) throw new Error('Failed to fetch calendar');
      const data = await response.json();
      setCalendarData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calendar');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const fetchReleaseDetail = async (releaseId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/calendar/release/${releaseId}`);
      if (!response.ok) throw new Error('Failed to fetch release detail');
      const data = await response.json();
      setReleaseDetail(data);
    } catch (err) {
      console.error('Failed to fetch release detail:', err);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'TBD';
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: 'America/New_York'
    });
  };

  const formatWeekRange = (releases: Release[]) => {
    if (releases.length === 0) return '';
    const dates = releases
      .filter(r => r.release_date)
      .map(r => new Date(r.release_date + 'T12:00:00'));
    if (dates.length === 0) return '';
    const first = dates[0];
    const last = dates[dates.length - 1];
    const startStr = first.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' });
    const endStr = last.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' });
    return startStr === endStr ? startStr : `${startStr} – ${endStr}`;
  };

  const formatNumber = (value: number | null, units?: string) => {
    if (value === null || value === undefined) return '-';
    const absValue = Math.abs(value);

    // Percentage-like values (< 20, typically rates)
    if (absValue < 20 && units !== 'index' && units !== 'thousands') {
      return value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
    }
    // Index values
    if (absValue < 1000) {
      return value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }
    // Large numbers - abbreviate
    if (absValue >= 1_000_000) {
      return (value / 1_000_000).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'M';
    }
    if (absValue >= 1000) {
      return (value / 1000).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + 'K';
    }
    return value.toLocaleString('en-US', { maximumFractionDigits: 1 });
  };

  const getImportanceBadge = (importance: string) => {
    const styles: Record<string, { bg: string; text: string; label: string }> = {
      high: { bg: 'bg-critical/20 border-critical/50', text: 'text-critical', label: 'HIGH' },
      medium: { bg: 'bg-warning/20 border-warning/50', text: 'text-warning', label: 'MEDIUM' },
      low: { bg: 'bg-neutral/20 border-neutral/50', text: 'text-neutral', label: 'LOW' }
    };
    return styles[importance] || styles.low;
  };

  const getDaysUntil = (dateStr: string | null) => {
    if (!dateStr) return null;
    const releaseDate = new Date(dateStr + 'T12:00:00');
    const today = new Date();
    today.setHours(12, 0, 0, 0);
    const diffTime = releaseDate.getTime() - today.getTime();
    return Math.round(diffTime / (1000 * 60 * 60 * 24));
  };

  const getCountdownLabel = (days: number | null) => {
    if (days === null) return null;
    if (days === 0) return { text: 'TODAY', style: 'bg-warning/20 text-warning border-warning/50' };
    if (days === 1) return { text: 'TOMORROW', style: 'bg-blue-500/20 text-blue-400 border-blue-500/50' };
    if (days < 0) return { text: 'RELEASED', style: 'bg-green-500/20 text-green-400 border-green-500/50' };
    return null;
  };

  const getDataPeriod = (release: Release) => {
    if (!release.previous_date) return null;
    const prevDate = new Date(release.previous_date + 'T12:00:00');
    return prevDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'America/New_York' });
  };

  const ReleaseCard: React.FC<{ release: Release }> = ({ release }) => {
    const daysUntil = getDaysUntil(release.release_date);
    const countdown = getCountdownLabel(daysUntil);
    const badge = getImportanceBadge(release.importance);
    const dataPeriod = getDataPeriod(release);
    const isSelected = selectedRelease === release.id;

    return (
      <div
        className={`bg-terminal-panel border rounded-lg p-4 cursor-pointer transition-all hover:border-neutral/60 ${
          isSelected ? 'border-neutral ring-1 ring-neutral/50' : 'border-terminal-border'
        } ${countdown?.text === 'TODAY' ? 'ring-1 ring-warning/40' : ''}`}
        onClick={() => setSelectedRelease(release.id)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded border font-medium ${badge.bg} ${badge.text}`}>
                {badge.label}
              </span>
              {countdown && (
                <span className={`text-xs px-2 py-0.5 rounded border font-medium ${countdown.style}`}>
                  {countdown.text}
                </span>
              )}
              {release.frequency === 'weekly' && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-terminal-border/50 text-terminal-text-dim">
                  Weekly
                </span>
              )}
            </div>
            <h3 className="font-semibold text-terminal-text text-sm">{release.name}</h3>
            <p className="text-xs text-terminal-text-dim mt-0.5">{release.description}</p>
          </div>

          <div className="text-right flex-shrink-0">
            <div className="flex items-center gap-1.5 text-sm text-terminal-text">
              <CalendarIcon className="w-3.5 h-3.5 text-terminal-text-dim" />
              <span className="font-mono text-xs">{formatDate(release.release_date)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-terminal-text-dim mt-1">
              <Clock className="w-3 h-3" />
              <span>{release.typical_time}</span>
            </div>
          </div>
        </div>

        {(release.previous_value !== null || release.consensus_estimate !== null) && (
          <div className="mt-3 pt-3 border-t border-terminal-border/50 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-terminal-text-dim text-xs block">
                Previous{dataPeriod ? ` (${dataPeriod})` : ''}
              </span>
              <span className="font-mono font-medium">{formatNumber(release.previous_value)}</span>
            </div>
            {release.consensus_estimate !== null && (
              <div>
                <span className="text-terminal-text-dim text-xs block">Consensus</span>
                <span className="font-mono font-medium">{formatNumber(release.consensus_estimate)}</span>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-end mt-1 text-terminal-text-dim">
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="flex items-center gap-3 text-terminal-text-dim">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span>Loading calendar...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-critical mx-auto mb-2" />
          <div className="text-critical mb-3">{error}</div>
          <button onClick={fetchCalendar} className="px-4 py-2 bg-neutral rounded hover:bg-blue-600 text-white text-sm">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const thisWeekRange = formatWeekRange(calendarData?.this_week || []);
  const nextWeekRange = formatWeekRange(calendarData?.next_week || []);

  return (
    <div className="min-h-screen bg-terminal-dark text-terminal-text">
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <CalendarIcon className="w-8 h-8 text-neutral" />
            <div>
              <h1 className="text-2xl font-bold">Economic Calendar</h1>
              <p className="text-terminal-text-dim text-sm">Upcoming data releases and economic events</p>
            </div>
          </div>
          <button
            onClick={fetchCalendar}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-1.5 rounded border border-terminal-border text-sm text-terminal-text-dim hover:text-terminal-text hover:border-neutral transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">This Week</div>
            <div className="text-3xl font-bold mt-1">{calendarData?.this_week.length || 0}</div>
            <div className="text-xs text-terminal-text-dim mt-1">releases</div>
          </div>
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">Next Week</div>
            <div className="text-3xl font-bold mt-1">{calendarData?.next_week.length || 0}</div>
            <div className="text-xs text-terminal-text-dim mt-1">releases</div>
          </div>
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">High Importance</div>
            <div className="text-3xl font-bold text-critical mt-1">{calendarData?.high_importance_count || 0}</div>
            <div className="text-xs text-terminal-text-dim mt-1">upcoming</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Release List */}
          <div className="lg:col-span-2 space-y-6">
            {/* This Week */}
            {calendarData?.this_week && calendarData.this_week.length > 0 && (
              <div>
                <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-warning"></span>
                  This Week
                  {thisWeekRange && (
                    <span className="text-sm font-normal text-terminal-text-dim">({thisWeekRange})</span>
                  )}
                </h2>
                <div className="space-y-3">
                  {calendarData.this_week.map(release => (
                    <ReleaseCard key={release.id} release={release} />
                  ))}
                </div>
              </div>
            )}

            {/* Next Week */}
            {calendarData?.next_week && calendarData.next_week.length > 0 && (
              <div>
                <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-neutral"></span>
                  Next Week
                  {nextWeekRange && (
                    <span className="text-sm font-normal text-terminal-text-dim">({nextWeekRange})</span>
                  )}
                </h2>
                <div className="space-y-3">
                  {calendarData.next_week.map(release => (
                    <ReleaseCard key={release.id} release={release} />
                  ))}
                </div>
              </div>
            )}

            {/* No releases */}
            {(!calendarData?.this_week?.length && !calendarData?.next_week?.length) && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-8 text-center">
                <CalendarIcon className="w-12 h-12 text-terminal-text-dim mx-auto mb-3 opacity-50" />
                <p className="text-terminal-text-dim">No upcoming releases in the next two weeks</p>
              </div>
            )}
          </div>

          {/* Release Detail Panel */}
          <div className="lg:col-span-1">
            <div className="bg-terminal-panel border border-terminal-border rounded-lg sticky top-20">
              {releaseDetail ? (
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${getImportanceBadge(releaseDetail.release.importance).bg} ${getImportanceBadge(releaseDetail.release.importance).text}`}>
                      {releaseDetail.release.importance.toUpperCase()}
                    </span>
                    <span className="text-xs text-terminal-text-dim capitalize">{releaseDetail.release.frequency}</span>
                  </div>
                  <h3 className="font-semibold text-lg mb-1">{releaseDetail.release.name}</h3>
                  <p className="text-sm text-terminal-text-dim mb-4">{releaseDetail.release.description}</p>

                  <div className="space-y-2 text-sm mb-4">
                    <div className="flex justify-between">
                      <span className="text-terminal-text-dim">FRED Series</span>
                      <span className="font-mono text-xs bg-terminal-border/30 px-1.5 py-0.5 rounded">{releaseDetail.release.series_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-terminal-text-dim">Typical Time</span>
                      <span>{releaseDetail.release.typical_time}</span>
                    </div>
                    {releaseDetail.release.release_date && (
                      <div className="flex justify-between">
                        <span className="text-terminal-text-dim">Next Release</span>
                        <span>{formatDate(releaseDetail.release.release_date)}</span>
                      </div>
                    )}
                  </div>

                  {/* History */}
                  {releaseDetail.history && releaseDetail.history.length > 0 && (
                    <div>
                      <h4 className="font-medium text-sm mb-2 text-terminal-text-dim uppercase tracking-wider">Recent Releases</h4>
                      <div className="border border-terminal-border/50 rounded overflow-hidden">
                        <div className="grid grid-cols-3 text-xs text-terminal-text-dim px-3 py-1.5 bg-terminal-border/20 border-b border-terminal-border/50">
                          <span>Date</span>
                          <span className="text-right">Value</span>
                          <span className="text-right">Change</span>
                        </div>
                        {releaseDetail.history.slice(0, 8).map((item, idx) => (
                          <div key={idx} className="grid grid-cols-3 items-center text-sm px-3 py-1.5 border-b border-terminal-border/30 last:border-0">
                            <span className="text-terminal-text-dim text-xs">
                              {new Date(item.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', year: '2-digit', timeZone: 'America/New_York' })}
                            </span>
                            <span className="font-mono text-right text-xs">{formatNumber(item.value)}</span>
                            <div className="text-right">
                              {item.change_percent !== null ? (
                                <span className={`text-xs font-mono ${item.change_percent >= 0 ? 'text-positive' : 'text-critical'}`}>
                                  {item.change_percent >= 0 ? '+' : ''}{item.change_percent.toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-xs text-terminal-text-dim">-</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center text-terminal-text-dim py-12 px-4">
                  <CalendarIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Select a release to view details</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
