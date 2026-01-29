import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Wifi, WifiOff, Bell, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface HeaderProps {
  connected: boolean;
  lastUpdate?: string;
  alertCount: number;
}

export const Header: React.FC<HeaderProps> = ({ connected, lastUpdate, alertCount }) => {
  const location = useLocation();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const formatLastUpdate = (timestamp?: string) => {
    if (!timestamp) return 'Never';

    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
      timeZone: 'America/New_York'
    });
  };

  const handleRefresh = async () => {
    if (refreshing) return;

    setRefreshing(true);
    setRefreshMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/refresh`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.status === 'started') {
        setRefreshMessage('Refreshing...');
        // Poll for completion
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`${API_URL}/api/refresh/status`);
            const statusData = await statusRes.json();
            if (!statusData.running) {
              clearInterval(pollInterval);
              setRefreshing(false);
              setRefreshMessage('Refresh complete!');
              setTimeout(() => setRefreshMessage(null), 3000);
            }
          } catch {
            clearInterval(pollInterval);
            setRefreshing(false);
          }
        }, 2000);
      } else if (data.status === 'already_running') {
        setRefreshMessage('Refresh in progress...');
      }
    } catch (error) {
      setRefreshing(false);
      setRefreshMessage('Refresh failed');
      setTimeout(() => setRefreshMessage(null), 3000);
    }
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="bg-terminal-panel border-b border-terminal-border sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo/Title */}
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
              <span className="text-2xl">📊</span>
              <div>
                <h1 className="text-xl font-bold text-terminal-text">
                  Economic Terminal
                </h1>
                <p className="text-xs text-terminal-text-dim">
                  Enterprise Risk Management
                </p>
              </div>
            </Link>

            {/* Navigation Links */}
            <nav className="hidden md:flex items-center gap-1">
              <Link
                to="/"
                className={`px-4 py-2 rounded transition-colors ${
                  isActive('/')
                    ? 'bg-neutral text-white'
                    : 'text-terminal-text-dim hover:text-terminal-text hover:bg-terminal-dark'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/historical"
                className={`px-4 py-2 rounded transition-colors ${
                  isActive('/historical')
                    ? 'bg-neutral text-white'
                    : 'text-terminal-text-dim hover:text-terminal-text hover:bg-terminal-dark'
                }`}
              >
                Historical Data
              </Link>
              <Link
                to="/calendar"
                className={`px-4 py-2 rounded transition-colors ${
                  isActive('/calendar')
                    ? 'bg-neutral text-white'
                    : 'text-terminal-text-dim hover:text-terminal-text hover:bg-terminal-dark'
                }`}
              >
                Calendar
              </Link>
            </nav>
          </div>

          {/* Status Indicators */}
          <div className="flex items-center gap-4">
            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
                refreshing
                  ? 'bg-terminal-dark text-terminal-text-dim cursor-not-allowed'
                  : 'bg-terminal-dark hover:bg-neutral text-terminal-text border border-terminal-border'
              }`}
              title="Refresh all data"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">
                {refreshMessage || 'Refresh'}
              </span>
            </button>

            {/* Alert Badge */}
            {alertCount > 0 && (
              <div className="relative">
                <Bell className="w-5 h-5 text-terminal-text-dim" />
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-critical rounded-full text-xs flex items-center justify-center font-bold">
                  {alertCount > 9 ? '9+' : alertCount}
                </span>
              </div>
            )}

            {/* Last Update */}
            <div className="hidden sm:flex items-center gap-2 text-sm text-terminal-text-dim">
              <RefreshCw className="w-4 h-4" />
              <span>Updated: {formatLastUpdate(lastUpdate)}</span>
            </div>
            
            {/* Connection Status */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
              connected 
                ? 'bg-positive/20 text-positive' 
                : 'bg-critical/20 text-critical'
            }`}>
              {connected ? (
                <>
                  <Wifi className="w-4 h-4" />
                  <span className="hidden sm:inline">Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4" />
                  <span className="hidden sm:inline">Offline</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
