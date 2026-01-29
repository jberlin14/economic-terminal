import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Search, ChevronDown, ChevronRight, X, Download, Plus, RefreshCw, Menu } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Indicator {
  series_id: string;
  name: string;
  report_group: string;
  category: string;
  units: string;
  frequency: string;
  latest_value?: number;
  latest_date?: string;
}

interface IndicatorsByReport {
  [reportGroup: string]: Indicator[];
}

interface DataPoint {
  date: string;
  value?: number;
  [key: string]: any; // For additional series or transforms
}

const DASHBOARDS = [
  { name: 'inflation', label: 'Inflation' },
  { name: 'labor', label: 'Labor Market' },
  { name: 'claims', label: 'Claims' },
  { name: 'gdp', label: 'GDP' },
];

const CHART_COLORS = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EC4899'];

export const HistoricalData: React.FC = () => {
  // State
  const [indicators, setIndicators] = useState<IndicatorsByReport>({});
  const [selectedSeries, setSelectedSeries] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<Indicator | null>(null);
  const [comparisonSeries, setComparisonSeries] = useState<string[]>([]);
  const [data, setData] = useState<DataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Controls state
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<string[]>(['Employment Situation']);
  const [transform, setTransform] = useState<string>('raw');
  const [movingAverages, setMovingAverages] = useState<number[]>([]);
  const [customMA, setCustomMA] = useState('');
  const [viewMode, setViewMode] = useState<'chart' | 'table' | 'both'>('chart');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [compareMode, setCompareMode] = useState(false);

  // Date range
  const [startDate, setStartDate] = useState(() => {
    const date = new Date();
    date.setFullYear(date.getFullYear() - 2);
    return date.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);

  // Load indicators on mount
  useEffect(() => {
    fetchIndicators();
  }, []);

  const fetchIndicators = async () => {
    try {
      const response = await fetch(`${API_URL}/api/indicators/`);
      if (!response.ok) throw new Error('Failed to fetch indicators');
      const data = await response.json();
      setIndicators(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load indicators');
    }
  };

  const fetchData = useCallback(async () => {
    if (!selectedSeries) return;

    setLoading(true);
    setError(null);

    try {
      let url: string;
      const maParams = movingAverages.length > 0 ? `&ma=${movingAverages.join(',')}` : '';

      if (comparisonSeries.length > 0) {
        // Fetch comparison data
        const allSeries = [selectedSeries!, ...comparisonSeries].join(',');
        url = `${API_URL}/api/indicators/compare?series=${allSeries}&start=${startDate}&end=${endDate}${transform !== 'raw' ? `&transform=${transform}` : ''}`;
      } else {
        // Fetch single series
        url = `${API_URL}/api/indicators/${selectedSeries}/history?start=${startDate}&end=${endDate}${transform !== 'raw' ? `&transform=${transform}` : ''}${maParams}`;
      }

      const response = await fetch(url);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch data' }));
        throw new Error(errorData.detail || 'Failed to fetch data');
      }
      const result = await response.json();

      setData(result.data || []);

      // Set selected indicator metadata if single series
      if (comparisonSeries.length === 0 && result.series_id) {
        setSelectedIndicator({
          series_id: result.series_id,
          name: result.name,
          units: result.units,
          frequency: result.frequency,
          report_group: '',
          category: '',
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load data';
      setError(errorMessage);

      // If comparison failed due to missing series, clear the comparison and refresh indicator list
      if (comparisonSeries.length > 0 && errorMessage.includes('not found')) {
        setComparisonSeries([]);
        setError(errorMessage + ' - Cleared invalid comparison series. Refreshing indicator list...');
        // Refresh the indicator list to remove deleted indicators
        fetchIndicators();
      }
    } finally {
      setLoading(false);
    }
  }, [selectedSeries, startDate, endDate, transform, movingAverages, comparisonSeries]);

  // Fetch data when selection changes
  useEffect(() => {
    if (selectedSeries) {
      fetchData();
    }
  }, [selectedSeries, fetchData]);

  const loadDashboard = async (dashboardName: string) => {
    setLoading(true);
    setError(null);
    setTransform('yoy_percent'); // Default to YoY % for dashboards

    try {
      const url = `${API_URL}/api/indicators/dashboard/${dashboardName}?start=${startDate}&end=${endDate}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch dashboard');
      const result = await response.json();

      if (result.series && result.series.length > 0) {
        // Set first series as selected
        setSelectedSeries(result.series[0].series_id);
        setSelectedIndicator(result.series[0]);

        // Set remaining series as comparison
        const compSeriesIds = result.series.slice(1).map((s: any) => s.series_id);
        setComparisonSeries(compSeriesIds);

        // Fetch comparison data for all series
        const allSeriesIds = result.series.map((s: any) => s.series_id).join(',');
        const dataUrl = `${API_URL}/api/indicators/compare?series=${allSeriesIds}&start=${startDate}&end=${endDate}&transform=yoy_percent`;
        const dataResponse = await fetch(dataUrl);
        if (!dataResponse.ok) throw new Error('Failed to fetch dashboard data');
        const dataResult = await dataResponse.json();

        setData(dataResult.data || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const exportToExcel = async (type: 'single' | 'comparison' | 'report') => {
    try {
      let url: string;

      switch (type) {
        case 'single':
          url = `${API_URL}/api/indicators/export/excel?series=${selectedSeries}&start=${startDate}&end=${endDate}`;
          break;
        case 'comparison':
          const allSeries = [selectedSeries!, ...comparisonSeries].join(',');
          url = `${API_URL}/api/indicators/export/excel?series=${allSeries}&start=${startDate}&end=${endDate}&format=columns`;
          break;
        case 'report':
          if (!selectedIndicator) return;
          url = `${API_URL}/api/indicators/export/excel/report/${encodeURIComponent(selectedIndicator.report_group)}?start=${startDate}&end=${endDate}`;
          break;
        default:
          return;
      }

      window.open(url, '_blank');
    } catch (err) {
      setError('Export failed');
    }
  };

  const refreshData = async () => {
    if (!selectedSeries) return;

    try {
      const response = await fetch(`${API_URL}/api/indicators/${selectedSeries}/refresh`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Refresh failed');

      // Refetch data
      await fetchData();
    } catch (err) {
      setError('Failed to refresh data');
    }
  };

  const toggleGroup = (group: string) => {
    setExpandedGroups(prev =>
      prev.includes(group) ? prev.filter(g => g !== group) : [...prev, group]
    );
  };

  const selectIndicator = (indicator: Indicator) => {
    if (compareMode) {
      // In compare mode, add to comparison
      if (!selectedSeries) {
        // If nothing selected yet, set this as the base series
        setSelectedSeries(indicator.series_id);
        setSelectedIndicator(indicator);
      } else if (indicator.series_id === selectedSeries) {
        // Clicking the base series does nothing in compare mode
        return;
      } else if (comparisonSeries.includes(indicator.series_id)) {
        // Remove from comparison if already added
        setComparisonSeries(comparisonSeries.filter(s => s !== indicator.series_id));
      } else {
        // Add to comparison
        setComparisonSeries([...comparisonSeries, indicator.series_id]);
      }
    } else {
      // Normal mode - replace current selection
      setSelectedSeries(indicator.series_id);
      setSelectedIndicator(indicator);
      setComparisonSeries([]);
    }
  };

  const removeComparison = (seriesId: string) => {
    setComparisonSeries(comparisonSeries.filter(s => s !== seriesId));
  };

  const addMA = (period: number) => {
    if (!movingAverages.includes(period)) {
      setMovingAverages([...movingAverages, period]);
    }
  };

  const removeMA = (period: number) => {
    setMovingAverages(movingAverages.filter(p => p !== period));
  };

  // Get all data keys for chart rendering (excluding 'date')
  const chartDataKeys = useMemo((): string[] => {
    if (data.length === 0) return [];

    const keys = Object.keys(data[0]).filter(k => k !== 'date');

    // If we're in comparison mode, return all series IDs
    if (comparisonSeries.length > 0) {
      return keys;
    }

    // If a transformation is selected, show only the transform column and MAs
    if (transform !== 'raw') {
      // Filter to show transformation column and moving averages
      const transformKey = transform; // e.g., 'yoy_percent', 'mom_change'
      const maKeys = keys.filter(k => k.startsWith('ma_'));

      // Check if the transform column exists in the data
      if (keys.includes(transformKey)) {
        return [transformKey, ...maKeys];
      }
    }

    // Otherwise, return value and any moving averages
    return keys;
  }, [data, comparisonSeries, transform]);

  // Format number with commas and appropriate decimal places
  const formatNumber = (value: number, forAxis: boolean = false): string => {
    if (value === null || value === undefined || isNaN(value)) return '-';

    const absValue = Math.abs(value);
    let decimals: number;

    // Determine decimal places based on magnitude
    if (absValue >= 1000) {
      decimals = forAxis ? 0 : 2;
    } else if (absValue >= 1) {
      decimals = 2;
    } else {
      decimals = 4;
    }

    return value.toLocaleString('en-US', {
      minimumFractionDigits: forAxis ? 0 : decimals,
      maximumFractionDigits: decimals
    });
  };

  // Calculate nice round tick values for Y-axis
  const niceNum = (range: number, round: boolean): number => {
    const exponent = Math.floor(Math.log10(range));
    const fraction = range / Math.pow(10, exponent);
    let niceFraction: number;

    if (round) {
      if (fraction < 1.5) niceFraction = 1;
      else if (fraction < 3) niceFraction = 2;
      else if (fraction < 7) niceFraction = 5;
      else niceFraction = 10;
    } else {
      if (fraction <= 1) niceFraction = 1;
      else if (fraction <= 2) niceFraction = 2;
      else if (fraction <= 5) niceFraction = 5;
      else niceFraction = 10;
    }

    return niceFraction * Math.pow(10, exponent);
  };

  // Calculate Y-axis domain for better chart scaling - only from displayed columns
  const yAxisDomain = useMemo((): [number, number] => {
    if (data.length === 0 || chartDataKeys.length === 0) return [0, 100];

    let allValues: number[] = [];

    // Only collect values from columns we're actually displaying
    data.forEach(row => {
      chartDataKeys.forEach(key => {
        const value = row[key];
        if (typeof value === 'number' && !isNaN(value) && value !== null) {
          allValues.push(value);
        }
      });
    });

    if (allValues.length === 0) return [0, 100];

    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const range = max - min || 1;

    // Calculate nice round boundaries
    const tickSpacing = niceNum(range / 5, true);
    const niceMin = Math.floor(min / tickSpacing) * tickSpacing;
    const niceMax = Math.ceil(max / tickSpacing) * tickSpacing;

    return [niceMin, niceMax];
  }, [data, chartDataKeys]);


  // Helper function to get indicator name from series ID
  const getIndicatorName = (seriesId: string): string => {
    // Search through all indicator groups
    for (const group of Object.values(indicators)) {
      const found = group.find((ind: Indicator) => ind.series_id === seriesId);
      if (found) return found.name;
    }
    return seriesId; // Fallback to series ID if not found
  };

  // Format column name for display
  const formatColumnName = (col: string): string => {
    if (col === 'value') return 'Value';
    if (col === 'yoy_percent') return 'YoY %';
    if (col === 'yoy_change') return 'YoY Change';
    if (col === 'mom_percent') return 'MoM %';
    if (col === 'mom_change') return 'MoM Change';
    if (col.startsWith('ma_')) {
      const period = col.split('_')[1];
      return `MA ${period}`;
    }
    // For series IDs in comparison mode, look up the full name
    return getIndicatorName(col);
  };

  const filteredIndicators = () => {
    if (!searchQuery) return indicators;

    const query = searchQuery.toLowerCase();
    const filtered: IndicatorsByReport = {};

    Object.entries(indicators).forEach(([group, inds]) => {
      const matchingInds = inds.filter(ind =>
        ind.name.toLowerCase().includes(query) ||
        ind.series_id.toLowerCase().includes(query)
      );
      if (matchingInds.length > 0) {
        filtered[group] = matchingInds;
      }
    });

    return filtered;
  };

  const renderSidebar = () => {
    const filtered = filteredIndicators();

    return (
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-terminal-panel border-r border-terminal-border flex-shrink-0 overflow-hidden`}>
        <div className="p-4">
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-terminal-text-dim" />
            <input
              type="text"
              placeholder="Search indicators..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-3 py-2 bg-terminal-dark border border-terminal-border rounded text-sm focus:outline-none focus:border-neutral"
            />
          </div>

          {/* Compare Mode Toggle */}
          <div className="mb-4 space-y-2">
            <button
              onClick={() => {
                setCompareMode(!compareMode);
                if (compareMode) {
                  // Exiting compare mode, clear comparisons
                  setComparisonSeries([]);
                }
              }}
              className={`w-full px-3 py-2 rounded text-sm font-medium transition-colors ${
                compareMode
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-terminal-dark hover:bg-neutral text-terminal-text border border-terminal-border'
              }`}
            >
              {compareMode ? (
                <div className="flex items-center justify-center gap-2">
                  <Plus className="w-4 h-4" />
                  <span>Compare Mode: ON</span>
                  {comparisonSeries.length > 0 && (
                    <span className="bg-blue-800 px-2 py-0.5 rounded-full text-xs">{comparisonSeries.length + 1}</span>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center gap-2">
                  <Plus className="w-4 h-4" />
                  <span>Enable Compare Mode</span>
                </div>
              )}
            </button>
            {compareMode && (
              <div className="text-xs text-terminal-text-dim text-center">
                Click indicators to add/remove from comparison
              </div>
            )}
            {comparisonSeries.length > 0 && (
              <button
                onClick={() => setComparisonSeries([])}
                className="w-full px-3 py-1.5 rounded text-sm bg-terminal-dark hover:bg-critical/20 text-critical border border-critical/50"
              >
                Clear All Comparisons
              </button>
            )}
          </div>

          {/* Report Groups */}
          <div className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto">
            {Object.entries(filtered).map(([group, groupIndicators]) => (
              <div key={group}>
                <button
                  onClick={() => toggleGroup(group)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-terminal-dark rounded text-left text-sm"
                >
                  {expandedGroups.includes(group) ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  <span className="font-medium">{group}</span>
                  <span className="text-terminal-text-dim text-xs ml-auto">({groupIndicators.length})</span>
                </button>

                {expandedGroups.includes(group) && (
                  <div className="ml-4 mt-1 space-y-1">
                    {groupIndicators.map(ind => (
                      <button
                        key={ind.series_id}
                        onClick={() => selectIndicator(ind)}
                        className={`w-full text-left px-2 py-1 rounded text-xs hover:bg-terminal-dark transition-colors ${
                          selectedSeries === ind.series_id
                            ? 'bg-neutral text-white'
                            : comparisonSeries.includes(ind.series_id)
                            ? 'bg-blue-900 text-white'
                            : compareMode
                            ? 'hover:bg-blue-900/30'
                            : ''
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">{ind.name}</div>
                            <div className="text-terminal-text-dim text-xs">{ind.series_id}</div>
                          </div>
                          <div className="flex-shrink-0">
                            {comparisonSeries.includes(ind.series_id) ? (
                              <span className="text-xs bg-blue-700 px-1.5 py-0.5 rounded flex items-center gap-1">
                                <X className="w-3 h-3" />
                                Remove
                              </span>
                            ) : compareMode && selectedSeries && ind.series_id !== selectedSeries ? (
                              <span className="text-xs bg-blue-600/50 px-1.5 py-0.5 rounded flex items-center gap-1">
                                <Plus className="w-3 h-3" />
                                Add
                              </span>
                            ) : selectedSeries === ind.series_id ? (
                              <span className="text-xs bg-neutral/50 px-1.5 py-0.5 rounded">Selected</span>
                            ) : null}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-terminal-dark text-terminal-text flex">
      {/* Sidebar */}
      {renderSidebar()}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="border-b border-terminal-border p-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-terminal-panel rounded"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="flex-1">
              <h1 className="text-2xl font-bold">Historical Economic Data</h1>
              {selectedIndicator && (
                <div className="text-sm text-terminal-text-dim mt-1">
                  {selectedIndicator.name} ({selectedIndicator.series_id}) - {selectedIndicator.units}
                </div>
              )}
            </div>

            {selectedSeries && (
              <button
                onClick={refreshData}
                className="px-3 py-2 bg-terminal-panel hover:bg-neutral border border-terminal-border rounded flex items-center gap-2"
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            )}
          </div>
        </div>

        {/* Dashboard Buttons */}
        <div className="border-b border-terminal-border p-4">
          <div className="flex gap-2 flex-wrap">
            {DASHBOARDS.map(dashboard => (
              <button
                key={dashboard.name}
                onClick={() => loadDashboard(dashboard.name)}
                className="px-4 py-2 bg-terminal-panel hover:bg-neutral border border-terminal-border rounded"
              >
                {dashboard.label}
              </button>
            ))}
          </div>
        </div>

        {!selectedSeries ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-terminal-text-dim">
              <p className="text-xl mb-2">Select an indicator to get started</p>
              <p className="text-sm">Choose from the sidebar or load a pre-configured dashboard</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Controls */}
            <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4 space-y-4">
              {/* Transform & Date Range */}
              <div className="flex gap-4 flex-wrap">
                <div>
                  <label className="block text-sm font-medium mb-1">Display</label>
                  <select
                    value={transform}
                    onChange={(e) => setTransform(e.target.value)}
                    className="px-3 py-2 bg-terminal-dark border border-terminal-border rounded"
                  >
                    <option value="raw">Raw</option>
                    <option value="yoy_percent">YoY %</option>
                    <option value="yoy_change">YoY Change</option>
                    <option value="mom_percent">MoM %</option>
                    <option value="mom_change">MoM Change</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="px-3 py-2 bg-terminal-dark border border-terminal-border rounded focus:outline-none focus:border-neutral focus:ring-1 focus:ring-neutral text-terminal-text [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-100 [&::-webkit-calendar-picker-indicator]:brightness-0 [&::-webkit-calendar-picker-indicator]:invert"
                    style={{ colorScheme: 'dark' }}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="px-3 py-2 bg-terminal-dark border border-terminal-border rounded focus:outline-none focus:border-neutral focus:ring-1 focus:ring-neutral text-terminal-text [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-100 [&::-webkit-calendar-picker-indicator]:brightness-0 [&::-webkit-calendar-picker-indicator]:invert"
                    style={{ colorScheme: 'dark' }}
                  />
                </div>
              </div>

              {/* Moving Averages */}
              <div>
                <label className="block text-sm font-medium mb-2">Moving Averages</label>
                <div className="flex gap-4 items-center flex-wrap">
                  {[3, 6, 12].map(period => (
                    <label key={period} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={movingAverages.includes(period)}
                        onChange={(e) => e.target.checked ? addMA(period) : removeMA(period)}
                        className="rounded"
                      />
                      <span>{period}-period</span>
                    </label>
                  ))}

                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      placeholder="Custom"
                      value={customMA}
                      onChange={(e) => setCustomMA(e.target.value)}
                      className="w-20 px-2 py-1 bg-terminal-dark border border-terminal-border rounded"
                    />
                    <button
                      onClick={() => {
                        const period = parseInt(customMA);
                        if (period > 0) {
                          addMA(period);
                          setCustomMA('');
                        }
                      }}
                      className="px-3 py-1 bg-neutral rounded text-sm"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>

              {/* View Mode */}
              <div className="flex gap-2">
                <button
                  onClick={() => setViewMode('chart')}
                  className={`px-4 py-2 rounded ${viewMode === 'chart' ? 'bg-neutral' : 'bg-terminal-dark'}`}
                >
                  Chart
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  className={`px-4 py-2 rounded ${viewMode === 'table' ? 'bg-neutral' : 'bg-terminal-dark'}`}
                >
                  Table
                </button>
                <button
                  onClick={() => setViewMode('both')}
                  className={`px-4 py-2 rounded ${viewMode === 'both' ? 'bg-neutral' : 'bg-terminal-dark'}`}
                >
                  Both
                </button>
              </div>

              {/* Compare Feature */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Compare Indicators
                  {compareMode && (
                    <span className="ml-2 text-xs bg-blue-600 text-white px-2 py-1 rounded">Mode Active</span>
                  )}
                </label>
                <div className="flex items-center gap-2 text-sm text-terminal-text-dim">
                  <Plus className="w-4 h-4" />
                  {compareMode ? (
                    <span>Compare mode is ON - Click indicators in sidebar to add/remove</span>
                  ) : (
                    <span>Enable "Compare Mode" in sidebar to compare multiple indicators</span>
                  )}
                </div>
              </div>
            </div>

            {/* Comparison Series Pills */}
            {comparisonSeries.length > 0 && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium">
                    Comparing {comparisonSeries.length + 1} Indicators
                  </h3>
                  <button
                    onClick={() => setComparisonSeries([])}
                    className="text-xs text-critical hover:text-critical/80 flex items-center gap-1"
                  >
                    <X className="w-3 h-3" />
                    Clear All
                  </button>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {/* Base series */}
                  {selectedIndicator && (
                    <div className="px-3 py-1.5 bg-neutral/20 border border-neutral rounded-full flex items-center gap-2">
                      <span className="text-xs font-medium">{selectedIndicator.name}</span>
                      <span className="text-xs text-terminal-text-dim">({selectedIndicator.series_id})</span>
                    </div>
                  )}
                  {/* Comparison series */}
                  {comparisonSeries.map((seriesId) => {
                    // Find indicator name from indicators list
                    let indicatorName = seriesId;
                    Object.values(indicators).forEach((group: any) => {
                      const found = group.find((ind: any) => ind.series_id === seriesId);
                      if (found) indicatorName = found.name;
                    });

                    return (
                      <div key={seriesId} className="px-3 py-1.5 bg-blue-900/30 border border-blue-700 rounded-full flex items-center gap-2">
                        <span className="text-xs font-medium">{indicatorName}</span>
                        <span className="text-xs text-terminal-text-dim">({seriesId})</span>
                        <button
                          onClick={() => removeComparison(seriesId)}
                          className="hover:bg-critical/20 rounded-full p-0.5"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Loading */}
            {loading && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-8 text-center">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-neutral" />
                <p className="text-terminal-text-dim">Loading data...</p>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="bg-critical/20 border border-critical rounded-lg p-4 text-critical">
                {error}
              </div>
            )}

            {/* Chart */}
            {!loading && (viewMode === 'chart' || viewMode === 'both') && data.length > 0 && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="date"
                      stroke="#9CA3AF"
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={60}
                    />
                    <YAxis
                      stroke="#9CA3AF"
                      domain={yAxisDomain}
                      tick={{ fontSize: 12 }}
                      tickFormatter={(value) => formatNumber(value, true)}
                      width={80}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                      labelStyle={{ color: '#D1D5DB' }}
                      formatter={(value: any) => typeof value === 'number' ? formatNumber(value) : value}
                    />
                    <Legend />

                    {chartDataKeys.map((key, idx) => (
                      <Line
                        key={key}
                        name={formatColumnName(key)}
                        type="monotone"
                        dataKey={key}
                        stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                        dot={false}
                        strokeWidth={key.startsWith('ma_') ? 1.5 : 2}
                        strokeDasharray={key.startsWith('ma_') ? '5 5' : undefined}
                        connectNulls={true}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Table */}
            {!loading && (viewMode === 'table' || viewMode === 'both') && data.length > 0 && (
              <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-terminal-border">
                        <th className="text-left p-2">Date</th>
                        {chartDataKeys.map(col => (
                          <th key={col} className="text-right p-2">{formatColumnName(col)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.slice(0, 50).map((row, idx) => (
                        <tr key={idx} className="border-b border-terminal-border/50 hover:bg-terminal-dark">
                          <td className="p-2">{row.date}</td>
                          {chartDataKeys.map(col => (
                            <td key={col} className="text-right p-2">
                              {typeof row[col] === 'number' ? formatNumber(row[col]) : (row[col] === null ? '-' : row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.length > 50 && (
                    <div className="text-center text-sm text-terminal-text-dim mt-4">
                      Showing first 50 of {data.length} rows
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Export */}
            <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
              <div className="flex gap-2">
                <button
                  onClick={() => exportToExcel('single')}
                  className="px-4 py-2 bg-neutral hover:bg-blue-600 rounded flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Export This Series
                </button>

                {comparisonSeries.length > 0 && (
                  <button
                    onClick={() => exportToExcel('comparison')}
                    className="px-4 py-2 bg-neutral hover:bg-blue-600 rounded flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Export Comparison
                  </button>
                )}

                <button
                  onClick={() => exportToExcel('report')}
                  className="px-4 py-2 bg-terminal-dark hover:bg-neutral border border-terminal-border rounded flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Export Report Group
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
