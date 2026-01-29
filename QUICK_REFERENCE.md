# Quick Reference Guide

## Essential Commands

### First Time Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your FRED_API_KEY

# 3. Run automated setup
python scripts/quick_start.py

# 4. Start backend
uvicorn backend.main:app --reload

# 5. Start frontend (new terminal)
cd frontend && npm install && npm start
```

---

## Daily Operations

### Backend
```bash
# Start backend (development)
uvicorn backend.main:app --reload

# Start backend (production)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Check health
python scripts/health_check.py
```

### Frontend
```bash
cd frontend

# Development
npm start

# Production build
npm run build

# Serve production build
npx serve -s build
```

---

## Data Management

### Fetch Latest Data
```bash
# All modules
python scripts/manual_fetch.py

# Indicators only
python scripts/init_indicators.py

# Specific indicator
python scripts/manual_fetch.py --indicators PAYEMS
```

### Check Data
```bash
# Comprehensive health check
python scripts/health_check.py

# Check specific series
python scripts/check_series.py PAYEMS UNRATE

# Test comparison
python scripts/test_comparison.py
```

---

## Database

### Initialize/Reset
```bash
# Initialize database
python scripts/init_db.py

# Add performance indexes
python scripts/add_indexes.py

# Migrate schema
python scripts/migrate_database.py
```

### Query
```bash
# Python shell
python

>>> from modules.data_storage.database import get_db_context
>>> from modules.economic_indicators.storage import IndicatorStorage
>>>
>>> with get_db_context() as db:
...     storage = IndicatorStorage(db)
...     indicators = storage.get_all_indicators()
...     print(f"Total: {len(indicators)}")
```

---

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Restart backend to reload modules
# Ctrl+C then re-run uvicorn
```

**Missing API Key**
```bash
# Check .env file
cat .env | grep FRED_API_KEY

# Test API connection
python -c "from modules.economic_indicators import IndicatorDataFetcher; f = IndicatorDataFetcher(); print('FRED API:', 'OK' if f.is_available() else 'FAIL')"
```

**Database Locked**
```bash
# Stop all backend processes
# Delete database and reinitialize
rm economic_data.db
python scripts/quick_start.py
```

**Frontend Build Errors**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

---

## Deployment (Render)

### Using Blueprint
```bash
# Deploy with render.yaml
render blueprint create
```

### Manual Deploy

**Backend:**
- Build Command: `pip install -r requirements.txt && python scripts/init_db.py`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Add disk at `/data`
- Set `DATABASE_URL=sqlite:////data/economic_data.db`

**Frontend:**
- Build Command: `npm install && npm run build`
- Publish Directory: `build`
- Set `REACT_APP_API_URL=https://your-backend.onrender.com`

### After Deployment
```bash
# In Render shell
python scripts/quick_start.py
```

---

## API Endpoints

### Health
- `GET /api/health` - System health check
- `GET /api/status` - Detailed status

### Indicators
- `GET /api/indicators` - All indicators grouped
- `GET /api/indicators/{series_id}` - Single indicator metadata
- `GET /api/indicators/{series_id}/history` - Historical data
- `GET /api/indicators/compare?series=A,B,C` - Compare indicators
- `GET /api/indicators/dashboard/{name}` - Dashboard data

### FX
- `GET /api/fx/rates` - All current rates
- `GET /api/fx/rates/{pair}` - Specific pair

### Yields
- `GET /api/yields/curve` - Current yield curve
- `GET /api/yields/history` - Historical curves

### News
- `GET /api/news` - Recent news articles
- `GET /api/news/search?q=term` - Search news

### Alerts
- `GET /api/risks/active` - Active alerts
- `GET /api/risks/critical` - Critical alerts

### Docs
- `GET /docs` - Interactive API documentation

---

## Environment Variables

### Required
```bash
DATABASE_URL=sqlite:///./economic_data.db
FRED_API_KEY=your_key_here
```

### Optional
```bash
ALPHA_VANTAGE_KEY=your_key_here
SENDGRID_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
TIMEZONE=America/New_York
LOG_LEVEL=INFO
DEBUG=false
```

---

## File Structure

```
economic-terminal/
├── backend/              # FastAPI backend
│   ├── api/             # API endpoints
│   ├── main.py          # Application entry
│   └── scheduler.py     # Background jobs
├── frontend/            # React frontend
│   └── src/
│       ├── pages/       # Page components
│       └── components/  # Reusable components
├── modules/             # Business logic
│   ├── economic_indicators/
│   ├── fx_monitor/
│   ├── yields_monitor/
│   ├── news_aggregator/
│   ├── risk_detector/
│   └── data_storage/
├── scripts/             # Utility scripts
├── .env                 # Environment config
├── requirements.txt     # Python dependencies
└── render.yaml          # Render deployment config
```

---

## Keyboard Shortcuts (Frontend)

- `Ctrl+K` / `Cmd+K` - Focus search
- Click indicator - Select for charting
- Compare Mode ON - Click to add/remove from comparison

---

## Tips & Best Practices

1. **Run health check daily**: `python scripts/health_check.py`
2. **Check logs regularly**: `tail -f logs/terminal_*.log`
3. **Update indicators weekly**: `python scripts/init_indicators.py`
4. **Monitor API rate limits**: FRED (120 req/min), Alpha Vantage (5 req/min)
5. **Backup database regularly**: `cp economic_data.db economic_data.db.backup`
6. **Keep dependencies updated**: `pip list --outdated`
7. **Test before deploying**: Run health check and test all features locally

---

## Getting Help

1. Check `IMPROVEMENTS.md` for recent changes
2. Check `RENDER_DEPLOYMENT.md` for deployment issues
3. Check `README.md` for general information
4. Review logs in `logs/` directory
5. Run `python scripts/health_check.py`
6. Check API docs at `/docs`

---

## Useful One-Liners

```bash
# Count indicators
python -c "from modules.data_storage.database import get_db_context; from modules.economic_indicators.storage import IndicatorStorage; db = get_db_context().__enter__(); print(f'{len(IndicatorStorage(db).get_all_indicators())} indicators')"

# Latest FX update
python -c "from modules.fx_monitor.storage import get_latest_update; u = get_latest_update(); print(f'Latest: {u.timestamp}' if u else 'No data')"

# Count news articles
python -c "from modules.news_aggregator.storage import get_recent_articles; print(f'{len(get_recent_articles(hours=24))} articles (24h)')"

# Active alerts
python -c "from modules.data_storage.database import get_db_context; from modules.risk_detector.alert_manager import AlertManager; db = get_db_context().__enter__(); print(f'{len(AlertManager(db).get_active_alerts())} active alerts')"

# Check timezone
python -c "from modules.utils.timezone import get_current_time, format_timestamp; print(format_timestamp())"
```

---

## Performance Tips

- Run `scripts/add_indexes.py` after large data imports
- Use date range filters on historical queries
- Limit news queries with `hours` or `limit` parameters
- Cache dashboard data on frontend (already implemented)
- Use transforms on server-side (already implemented)

---

## Version Info

- Python: 3.11+
- Node.js: 18+
- FastAPI: 0.109.0+
- React: 18
- Timezone: America/New_York (US Eastern)
- Database: SQLite (dev), PostgreSQL (prod recommended)

---

*Last Updated: 2026-01-26*
