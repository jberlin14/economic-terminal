import React from 'react';
import { AlertTriangle, AlertCircle, Bell, X } from 'lucide-react';

interface RiskAlert {
  id: number;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  triggered_at: string;
  related_entity?: string;
  acknowledged?: boolean;
}

interface RiskAlertPanelProps {
  alerts: RiskAlert[];
  onDismiss?: (id: number) => void;
}

export const RiskAlertPanel: React.FC<RiskAlertPanelProps> = ({ alerts, onDismiss }) => {
  const criticalAlerts = alerts.filter(a => a.severity === 'CRITICAL');
  const highAlerts = alerts.filter(a => a.severity === 'HIGH');
  
  if (alerts.length === 0) {
    return null;
  }

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return {
          bg: 'bg-critical/20',
          border: 'border-critical',
          text: 'text-critical',
          icon: AlertTriangle
        };
      case 'HIGH':
        return {
          bg: 'bg-warning/20',
          border: 'border-warning',
          text: 'text-warning',
          icon: AlertCircle
        };
      default:
        return {
          bg: 'bg-neutral/20',
          border: 'border-neutral',
          text: 'text-neutral',
          icon: Bell
        };
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const getTypeEmoji = (type: string) => {
    switch (type) {
      case 'FX': return '💱';
      case 'YIELDS': return '📈';
      case 'CREDIT': return '💳';
      case 'POLITICAL': return '🌍';
      case 'ECON': return '📊';
      case 'CAT': return '🌪️';
      default: return '⚠️';
    }
  };

  return (
    <div className="space-y-3">
      {criticalAlerts.map(alert => {
        const styles = getSeverityStyles(alert.severity);
        const Icon = styles.icon;
        
        return (
          <div 
            key={alert.id}
            className={`${styles.bg} border-2 ${styles.border} rounded-lg p-4 animate-pulse-alert`}
          >
            <div className="flex items-start gap-3">
              <Icon className={`w-6 h-6 ${styles.text} flex-shrink-0 mt-0.5`} />
              
              <div className="flex-grow">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`font-bold ${styles.text}`}>CRITICAL</span>
                  <span>{getTypeEmoji(alert.alert_type)}</span>
                  <span className="text-sm text-terminal-text-dim">{alert.alert_type}</span>
                  <span className="text-xs text-terminal-text-dim ml-auto">
                    {formatTime(alert.triggered_at)}
                  </span>
                </div>
                
                <div className="font-semibold mb-1">{alert.title}</div>
                <div className="text-sm text-terminal-text-dim">{alert.message}</div>
              </div>
              
              {onDismiss && (
                <button 
                  onClick={() => onDismiss(alert.id)}
                  className="text-terminal-text-dim hover:text-terminal-text"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        );
      })}

      {highAlerts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {highAlerts.map(alert => {
            const styles = getSeverityStyles(alert.severity);
            const Icon = styles.icon;
            
            return (
              <div 
                key={alert.id}
                className={`${styles.bg} border ${styles.border} rounded-lg p-3`}
              >
                <div className="flex items-start gap-2">
                  <Icon className={`w-5 h-5 ${styles.text} flex-shrink-0`} />
                  <div className="flex-grow min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <span className={`font-bold ${styles.text}`}>HIGH</span>
                      <span>{getTypeEmoji(alert.alert_type)}</span>
                      <span className="text-terminal-text-dim truncate">{alert.title}</span>
                    </div>
                    <div className="text-sm text-terminal-text-dim truncate mt-1">
                      {alert.message}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
