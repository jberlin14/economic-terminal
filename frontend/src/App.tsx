import React, { useEffect, useState } from 'react';
import { FXDashboard } from './components/FXDashboard';
import { YieldCurveChart } from './components/YieldCurveChart';
import { CreditSpreadsPanel } from './components/CreditSpreadsPanel';
import { RiskAlertPanel } from './components/RiskAlertPanel';
import { NewsFeed } from './components/NewsFeed';
import { Header } from './components/Header';
import { useWebSocket } from './hooks/useWebSocket';
import './styles/globals.css';

interface DashboardData {
  fx_rates: any[];
  yield_curve: any;
  credit_spreads: any[];
  active_alerts: any[];
  recent_news: any[];
  timestamp: string;
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws');

  // Fetch initial dashboard data
  useEffect(() => {
    fetchDashboard();
    
    // Refresh every 5 minutes
    const interval = setInterval(fetchDashboard, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Handle WebSocket updates
  useEffect(() => {
    if (lastMessage) {
      if (lastMessage.type === 'fx_update' && data) {
        setData(prev => prev ? {
          ...prev,
          fx_rates: lastMessage.data.rates,
          timestamp: lastMessage.timestamp || prev.timestamp
        } : null);
      } else if (lastMessage.type === 'yield_update' && data) {
        // Check if this is credit spreads or yield curve
        if (lastMessage.data.type === 'credit_spreads') {
          setData(prev => prev ? {
            ...prev,
            credit_spreads: lastMessage.data.spreads,
            timestamp: lastMessage.timestamp || prev.timestamp
          } : null);
        } else {
          setData(prev => prev ? {
            ...prev,
            yield_curve: lastMessage.data,
            timestamp: lastMessage.timestamp || prev.timestamp
          } : null);
        }
      } else if (lastMessage.type === 'alert' && data) {
        setData(prev => prev ? {
          ...prev,
          active_alerts: [lastMessage.data, ...prev.active_alerts]
        } : null);
      }
    }
  }, [lastMessage, data]);

  const fetchDashboard = async () => {
    try {
      const response = await fetch('/api/dashboard');
      if (!response.ok) throw new Error('Failed to fetch dashboard');
      const dashboardData = await response.json();
      setData(dashboardData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="text-terminal-text text-xl">
          <div className="animate-pulse">Loading Economic Terminal...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-terminal-dark flex items-center justify-center">
        <div className="text-center">
          <div className="text-critical text-xl mb-4">Error: {error}</div>
          <button 
            onClick={fetchDashboard}
            className="px-4 py-2 bg-neutral rounded hover:bg-blue-600 text-white"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-terminal-dark text-terminal-text">
      <Header 
        connected={connected} 
        lastUpdate={data?.timestamp} 
        alertCount={data?.active_alerts?.length || 0}
      />
      
      <main className="container mx-auto px-4 py-6">
        {/* Risk Alerts Banner */}
        {data?.active_alerts && data.active_alerts.length > 0 && (
          <div className="mb-6">
            <RiskAlertPanel alerts={data.active_alerts} />
          </div>
        )}
        
        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* FX Dashboard - Full width on mobile, half on desktop */}
          <div className="lg:col-span-1">
            <FXDashboard rates={data?.fx_rates || []} />
          </div>

          {/* Yield Curve */}
          <div className="lg:col-span-1">
            <YieldCurveChart curve={data?.yield_curve} />
          </div>
        </div>

        {/* Credit Spreads - Full width */}
        <div className="mt-6">
          <CreditSpreadsPanel spreads={data?.credit_spreads || []} />
        </div>

        {/* News Feed - Full width */}
        <div className="mt-6">
          <NewsFeed articles={data?.recent_news || []} />
        </div>
      </main>
      
      {/* Footer */}
      <footer className="border-t border-terminal-border py-4 mt-8">
        <div className="container mx-auto px-4 text-center text-terminal-text-dim text-sm">
          Economic Terminal v1.0.0 | Data updates every 5 minutes
        </div>
      </footer>
    </div>
  );
}

export default App;
