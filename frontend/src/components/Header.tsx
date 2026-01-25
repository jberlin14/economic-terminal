import React from 'react';
import { Wifi, WifiOff, Bell, RefreshCw } from 'lucide-react';

interface HeaderProps {
  connected: boolean;
  lastUpdate?: string;
  alertCount: number;
}

export const Header: React.FC<HeaderProps> = ({ connected, lastUpdate, alertCount }) => {
  const formatLastUpdate = (timestamp?: string) => {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  return (
    <header className="bg-terminal-panel border-b border-terminal-border sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo/Title */}
          <div className="flex items-center gap-3">
            <span className="text-2xl">📊</span>
            <div>
              <h1 className="text-xl font-bold text-terminal-text">
                Economic Terminal
              </h1>
              <p className="text-xs text-terminal-text-dim">
                Enterprise Risk Management
              </p>
            </div>
          </div>
          
          {/* Status Indicators */}
          <div className="flex items-center gap-4">
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
