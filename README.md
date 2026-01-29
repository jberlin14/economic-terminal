# Economic Terminal

A professional-grade economic monitoring dashboard for Enterprise Risk Management. Built as a personal Bloomberg Terminal alternative with real-time monitoring, risk detection, and automated reporting capabilities.

## Features

### Data Monitoring
- **FX Rates**: Real-time tracking of 11 currency pairs (USD/XXX convention)
- **Treasury Yields**: Complete US yield curve with spread calculations
- **Credit Spreads**: Investment Grade and High Yield spreads with percentile analysis
- **Economic Data**: Key indicators with surprise detection
- **News Aggregation**: Multi-source news with severity tagging

### Risk Detection
- **FX Volatility**: Alerts for moves >1% (HIGH) or >2% (CRITICAL)
- **Yield Curve Inversion**: Automatic detection with depth analysis
- **Credit Stress**: Percentile-based alerts (90th/95th thresholds)
- **Geopolitical Events**: Keyword-based critical news detection

### Notifications
- **Real-time WebSocket**: Live updates to dashboard
- **Email Alerts**: Immediate notification for CRITICAL alerts
- **Daily Digest**: 7 AM summary of overnight developments

## Architecture

```
economic-terminal/
├── modules/                 # Data collection modules
│   ├── fx_monitor/         # FX rate tracking
│   ├── yields_monitor/     # Treasury yield curves
│   ├── credit_monitor/     # Credit spreads
│   ├── economic_data/      # Economic indicators
│   ├── news_aggregator/    # News collection
│   ├── risk_detector/      # Alert generation
│   ├── email_reporter/     # Email notifications
│   └── data_storage/       # Database management
├── backend/                # FastAPI application
│   ├── api/               # REST API endpoints
│   ├── main.py            # Application entry point
│   ├── scheduler.py       # Background jobs
│   └── websocket.py       # Real-time updates
├── frontend/              # React dashboard
├── scripts/               # Setup and utility scripts
└── deployment/            # Docker and Render configs
```

## Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL (production) / SQLite (development)
- **Frontend**: React 18 with TypeScript
- **Styling**: TailwindCSS (dark theme)
- **Charts**: Recharts
- **Real-time**: WebSockets
- **Scheduling**: APScheduler
- **Email**: SendGrid

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Quick Start (Recommended)

1. **Clone and setup environment**:
```bash
git clone https://github.com/yourusername/economic-terminal.git
cd economic-terminal

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your API keys (at minimum: FRED_API_KEY)
```

3. **Run automated setup**:
```bash
python scripts/quick_start.py
```
This automated script will:
- Verify environment configuration
- Initialize database with proper indexes
- Fetch economic indicator data (69 series)
- Run comprehensive health checks

4. **Start the application**:
```bash
# Start backend
uvicorn backend.main:app --reload

# In another terminal, start frontend
cd frontend
npm install
npm start
```

Visit `http://localhost:3000` for the dashboard, `http://localhost:8000/docs` for API docs.

### Manual Installation

If you prefer manual setup or need to troubleshoot:

```bash
# Initialize database
python scripts/init_db.py

# Add performance indexes
python scripts/add_indexes.py

# Initialize economic indicators
python scripts/init_indicators.py

# Run health check
python scripts/health_check.py
```

## API Keys Required

| Service | Purpose | Get Free Key |
|---------|---------|--------------|
| Alpha Vantage | FX rates | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| FRED | Economic data | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |
| SendGrid | Email alerts | [sendgrid.com](https://sendgrid.com/free/) |

## API Endpoints

### Dashboard
- `GET /api/dashboard` - Complete dashboard data
- `GET /api/status` - System status

### FX Rates
- `GET /api/fx/rates` - All current rates
- `GET /api/fx/rates/{pair}` - Specific pair
- `GET /api/fx/history/{pair}` - Historical rates
- `GET /api/fx/movers` - Biggest movers

### Yields
- `GET /api/yields/curve` - Current yield curve
- `GET /api/yields/history` - Historical curves
- `GET /api/yields/analysis` - Curve analysis

### Risk Alerts
- `GET /api/risks/active` - Active alerts
- `GET /api/risks/critical` - Critical alerts only
- `POST /api/risks/{id}/resolve` - Resolve alert

## Country/Region Priority

1. United States
2. Japan
3. Canada
4. Mexico
5. Eurozone
6. Brazil
7. Argentina
8. United Kingdom
9. Australia
10. New Zealand
11. Taiwan

## Risk Type Hierarchy

1. **ECON** - Economic data surprises
2. **FX** - Currency volatility
3. **POLITICAL** - Geopolitical developments
4. **CREDIT** - Credit market stress
5. **CAT** - Catastrophic events

## Deployment

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed deployment instructions to Render.com.

## Development

### Useful Scripts

```bash
# Quick automated setup
python scripts/quick_start.py

# Comprehensive system health check
python scripts/health_check.py

# Initialize economic indicators
python scripts/init_indicators.py

# Add database performance indexes
python scripts/add_indexes.py

# Manual data fetch
python scripts/manual_fetch.py

# Check specific indicator series
python scripts/check_series.py PAYEMS UNRATE

# Test comparison feature
python scripts/test_comparison.py

# Clean up failed indicators
python scripts/cleanup_failed_indicators.py
```

### Testing
```bash
# Run all module tests
python scripts/test_modules.py

# Run specific module test
python scripts/test_modules.py --module fx

# Test news aggregator
python scripts/test_news_aggregator.py

# Test credit monitor
python scripts/test_credit_monitor.py
```

### Adding New Modules

Each module should follow the structure:
```
modules/new_module/
├── __init__.py
├── config.py      # Configuration
├── models.py      # Pydantic models
├── data_fetcher.py # API integration
├── storage.py     # Database operations
└── test.py        # Module tests
```

## License

MIT License - see LICENSE file for details.

## Acknowledgments

Built for ERM economic monitoring workflows. Designed to replace expensive terminal subscriptions with a customizable, open-source alternative.
