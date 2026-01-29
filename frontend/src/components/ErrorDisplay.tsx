import React from 'react';
import { AlertCircle, RefreshCw, X } from 'lucide-react';

interface ErrorDisplayProps {
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  severity?: 'error' | 'warning' | 'info';
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  message,
  onRetry,
  onDismiss,
  severity = 'error'
}) => {
  const severityStyles = {
    error: 'bg-red-900/20 border-red-700 text-red-300',
    warning: 'bg-yellow-900/20 border-yellow-700 text-yellow-300',
    info: 'bg-blue-900/20 border-blue-700 text-blue-300'
  };

  return (
    <div className={`rounded-lg border p-4 ${severityStyles[severity]}`}>
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm">{message}</p>
          {(onRetry || onDismiss) && (
            <div className="flex gap-2 mt-3">
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="flex items-center gap-1 px-3 py-1 text-xs bg-terminal-border hover:bg-terminal-border/70 rounded transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                  Retry
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  className="flex items-center gap-1 px-3 py-1 text-xs bg-terminal-border hover:bg-terminal-border/70 rounded transition-colors"
                >
                  <X className="w-3 h-3" />
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
