#!/usr/bin/env bash
#
# Render Start Script
# Starts the FastAPI application on Render.com
#

set -e  # Exit on error

echo "========================================="
echo "Economic Terminal - Starting"
echo "========================================="

# Create logs directory if it doesn't exist
mkdir -p logs

# Print environment info
echo "Environment:"
echo "  DATABASE_URL: ${DATABASE_URL:-Not set}"
echo "  FRED_API_KEY: ${FRED_API_KEY:+Configured}"
echo "  ALPHA_VANTAGE_KEY: ${ALPHA_VANTAGE_KEY:+Configured}"
echo "  TIMEZONE: ${TIMEZONE:-America/New_York}"
echo "  PORT: ${PORT:-8000}"
echo ""

# Start the application
echo "Starting FastAPI application..."
exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level info \
    --no-access-log
