import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { HistoricalData } from './pages/HistoricalData';
import { Calendar } from './pages/Calendar';
import { useWebSocket } from './hooks/useWebSocket';
import './styles/globals.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

function App() {
  const { connected, lastMessage } = useWebSocket(WS_URL);
  const [alertCount, setAlertCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string | undefined>(undefined);

  // Track alert count from WebSocket
  useEffect(() => {
    if (lastMessage && lastMessage.type === 'alert') {
      setAlertCount(prev => prev + 1);
    }
    if (lastMessage && lastMessage.timestamp) {
      setLastUpdate(lastMessage.timestamp);
    }
  }, [lastMessage]);

  return (
    <Router>
      <div className="min-h-screen bg-terminal-dark text-terminal-text">
        <Header
          connected={connected}
          lastUpdate={lastUpdate}
          alertCount={alertCount}
        />

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/historical" element={<HistoricalData />} />
          <Route path="/calendar" element={<Calendar />} />
        </Routes>

        {/* Footer */}
        <footer className="border-t border-terminal-border py-4 mt-8">
          <div className="container mx-auto px-4 text-center text-terminal-text-dim text-sm">
            Economic Terminal v1.0.0 | Data updates every 5 minutes
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
