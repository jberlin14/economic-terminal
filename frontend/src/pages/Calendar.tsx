import React, { useEffect, useState } from 'react';
import { Calendar as CalendarIcon, Clock, TrendingUp, TrendingDown, AlertCircle, ChevronRight } from 'lucide-react';

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
      const response = await fetch(`${API_URL}/api/calendar/`);
      if (!response.ok) throw new Error('Failed to fetch calendar');
      const data = await response.json();
      setCalendarData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calendar');
    } finally {
      setLoading(false);
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
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: 'America/New_York'
    });
  };

  const formatNumber = (value: number | null, decimals: number = 2) => {
    if (value === null || value === undefined) return '-';
    const absValue = Math.abs(value);
    if (absValue >= 1000) {
      return value.toLocaleString('en-US', { maximumFractionDigits: 1 });
    }
    return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const getImportanceBadge = (importance: string) => {
    const styles = {
      high: 'bg-critical/20 text-critical border-critical/50',
      medium: 'bg-warning/20 text-warning border-warning/50',
      low: 'bg-neutral/20 text-neutral border-neutral/50'
    };
    return styles[importance as keyof typeof styles] || styles.low;
  };

  const getDaysUntil = (dateStr: string | null) => {
    if (!dateStr) return null;
    const releaseDate = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    releaseDate.setHours(0, 0, 0, 0);
    const diffTime = releaseDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const ReleaseCard: React.FC<{ release: Release; showDetail?: boolean }> = ({ release, showDetail = true }) => {
    const daysUntil = getDaysUntil(release.release_date);
    const isToday = daysUntil === 0;
    const isTomorrow = daysUntil === 1;

    return (
      <div
        className={`bg-terminal-panel border rounded-lg p-4 cursor-pointer transition-all hover:border-neutral ${
          selectedRelease === release.id ? 'border-neutral ring-1 ring-neutral' : 'border-terminal-border'
        } ${isToday ? 'ring-2 ring-warning/50' : ''}`}
        onClick={() => setSelectedRelease(release.id)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs px-2 py-0.5 rounded border ${getImportanceBadge(release.importance)}`}>
                {release.importance.toUpperCase()}
              </span>
              {isToday && (
                <span className="text-xs px-2 py-0.5 rounded bg-warning/20 text-warning border border-warning/50">
                  TODAY
                </span>
              )}
              {isTomorrow && (
                <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/50">
                  TOMORROW
                </span>
              )}
            </div>
            <h3 className="font-semibold text-terminal-text">{release.name}</h3>
            <p className="text-sm text-terminal-text-dim mt-1">{release.description}</p>
          </div>

          <div className="text-right flex-shrink-0">
            <div className="flex items-center gap-1 text-sm text-terminal-text-dim">
              <CalendarIcon className="w-4 h-4" />
              <span>{formatDate(release.release_date)}</span>
            </div>
            <div className="flex items-center gap-1 text-xs text-terminal-text-dim mt-1">
              <Clock className="w-3 h-3" />
              <span>{release.typical_time}</span>
            </div>
          </div>
        </div>

        {showDetail && release.previous_value !== null && (
          <div className="mt-3 pt-3 border-t border-terminal-border">
            <div className="flex items-center justify-between text-sm">
              <span className="text-terminal-text-dim">Previous:</span>
              <span className="font-mono">{formatNumber(release.previous_value)}</span>
            </div>
            {release.consensus_estimate !== null && (
              <div className="flex items-center justify-between text-sm mt-1">
                <span className="text-terminal-text-dim">Consensus:</span>
                <span className="font-mono">{formatNumber(release.consensus_estimate)}</span>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-end mt-2 text-terminal-text-dim">
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="text-terminal-text-dim">Loading calendar...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="text-critical">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-terminal-dark text-terminal-text">
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <CalendarIcon className="w-8 h-8 text-neutral" />
          <div>
            <h1 className="text-2xl font-bold">Economic Calendar</h1>
            <p className="text-terminal-text-dim">Upcoming data releases and economic events</p>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">This Week</div>
            <div className="text-2xl font-bold">{calendarData?.this_week.length || 0}</div>
            <div className="text-xs text-terminal-text-dim">releases</div>
          </div>
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">Next Week</div>
            <div className="text-2xl font-bold">{calendarData?.next_week.length || 0}</div>
            <div className="text-xs text-terminal-text-dim">releases</div>
          </div>
          <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
            <div className="text-sm text-terminal-text-dim">High Importance</div>
            <div className="text-2xl font-bold text-critical">{calendarData?.high_importance_count || 0}</div>
            <div className="text-xs text-terminal-text-dim">upcoming</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Release List */}
          <div className="lg:col-span-2 space-y-6">
            {/* This Week */}
            {calendarData?.this_week && calendarData.this_week.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-warning"></span>
                  This Week
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
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-neutral"></span>
                  Next Week
                </h2>
                <div className="space-y-3">
                  {calendarData.next_week.map(release => (
                    <ReleaseCard key={release.id} release={release} />
                  ))}
                </div>
              </div>
            )}

            {/* No releases message */}
            {(!calendarData?.this_week?.length && !calendarData?.next_week?.length) && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-8 text-center">
                <AlertCircle className="w-12 h-12 text-terminal-text-dim mx-auto mb-3" />
                <p className="text-terminal-text-dim">No upcoming releases in the next two weeks</p>
              </div>
            )}
          </div>

          {/* Release Detail Panel */}
          <div className="lg:col-span-1">
            <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4 sticky top-20">
              {releaseDetail ? (
                <>
                  <h3 className="font-semibold text-lg mb-2">{releaseDetail.release.name}</h3>
                  <p className="text-sm text-terminal-text-dim mb-4">{releaseDetail.release.description}</p>

                  <div className="space-y-2 text-sm mb-4">
                    <div className="flex justify-between">
                      <span className="text-terminal-text-dim">Series ID:</span>
                      <span className="font-mono">{releaseDetail.release.series_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-terminal-text-dim">Frequency:</span>
                      <span className="capitalize">{releaseDetail.release.frequency}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-terminal-text-dim">Typical Time:</span>
                      <span>{releaseDetail.release.typical_time}</span>
                    </div>
                  </div>

                  {/* History */}
                  {releaseDetail.history && releaseDetail.history.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2">Recent History</h4>
                      <div className="space-y-1">
                        {releaseDetail.history.slice(0, 6).map((item, idx) => (
                          <div key={idx} className="flex items-center justify-between text-sm py-1 border-b border-terminal-border/50">
                            <span className="text-terminal-text-dim">{formatDate(item.date)}</span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono">{formatNumber(item.value)}</span>
                              {item.change_percent !== null && (
                                <span className={`text-xs ${item.change_percent >= 0 ? 'text-positive' : 'text-critical'}`}>
                                  {item.change_percent >= 0 ? (
                                    <TrendingUp className="w-3 h-3 inline" />
                                  ) : (
                                    <TrendingDown className="w-3 h-3 inline" />
                                  )}
                                  {' '}{Math.abs(item.change_percent).toFixed(1)}%
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-terminal-text-dim py-8">
                  <CalendarIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Select a release to view details</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
