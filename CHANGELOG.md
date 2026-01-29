# Changelog

All notable changes to the Economic Terminal project.

## [Unreleased] - 2026-01-26

### Added
- **Timezone Support**: Centralized timezone handling using US Eastern time
  - Created `modules/utils/timezone.py` with timezone utilities
  - All timestamps now use America/New_York timezone
  - Added market hours detection
  - Scheduler already configured for Eastern timezone

- **UI Components**:
  - `LoadingSpinner` component for better loading states
  - `ErrorDisplay` component for consistent error messages
  - Improved indicator name display in chart legends (full names instead of series IDs)

- **Developer Scripts**:
  - `scripts/health_check.py` - Comprehensive system health check
  - `scripts/quick_start.py` - Automated first-time setup
  - `scripts/add_indexes.py` - Database performance indexes
  - `scripts/check_series.py` - Diagnostic tool for indicator series
  - `scripts/test_comparison.py` - Test comparison feature

- **Deployment Tools**:
  - `render.yaml` - Infrastructure as Code for Render deployment
  - `Procfile` - Process configuration
  - `scripts/render_build.sh` - Build script for Render
  - `scripts/render_start.sh` - Start script for Render

- **Error Handling**:
  - `backend/api/error_handlers.py` - Centralized error handling
  - Consistent error response format across all endpoints
  - Better logging for debugging

- **Database Improvements**:
  - Added performance indexes for common queries
  - Optimized news article searches
  - Improved risk alert filtering
  - Faster historical data queries

### Fixed
- **Comparison Feature**: Fixed route order bug where `/compare` endpoint was matched as `/{series_id}`
  - Moved `/compare` endpoint before `/{series_id}` in indicators API
  - Comparison now works correctly for all series pairs

- **Chart Legends**: Now display full indicator names instead of series IDs (e.g., "Average Weekly Hours (Private)" instead of "AWHAETP")

- **Y-axis Scaling**: Chart Y-axis now properly adjusts based on visible data columns

- **Date Picker**: Calendar icon now bright white and visible in dark mode

- **Transformations**: Fixed NaN serialization errors when applying YoY, MoM, and MA transformations
  - Added NaN to None conversion before JSON serialization
  - Charts now properly display transformed data with `connectNulls={true}`

### Changed
- **Compare Mode UX**: Redesigned comparison feature
  - Added toggle button for Compare Mode
  - Visual indicators ("+Add", "X Remove", "Selected" badges)
  - No longer requires Ctrl/Cmd+Click
  - Clearer user feedback

- **Logging**: Added detailed logging to comparison data retrieval for debugging

- **Backend Main**: Updated to use timezone utility for consistent timestamp handling

### Technical Improvements
- Database schema already has proper indexes on critical fields
- All datetime operations now timezone-aware
- Better error messages with actionable information
- Comprehensive health checks for all modules
- Improved code organization with utility modules

### Documentation
- Updated README with comprehensive feature list
- Added this CHANGELOG for version tracking
- Render deployment guide already comprehensive
- Added inline code documentation

### Performance
- Database indexes on frequently queried fields:
  - News articles: timestamp, source, severity
  - Risk alerts: status, severity, created_at
  - FX/Yields/Credit: timestamp DESC for latest data queries
  - Indicator values: date range queries

### Dependencies
- All dependencies already in requirements.txt
- pytz for timezone handling (already included)
- No new dependencies added

## Pre-existing Features (before this update)

### Core Modules
- FX Monitor with Alpha Vantage integration
- Yields Monitor with Treasury.gov data
- Credit Monitor with FRED spreads
- News Aggregator with RSS feeds and leader detection
- Risk Detector with multi-source alert generation
- Economic Indicators with 69 FRED series

### Infrastructure
- FastAPI backend with WebSocket support
- React TypeScript frontend with dark theme
- SQLAlchemy ORM with PostgreSQL/SQLite
- APScheduler for background jobs
- Comprehensive API endpoints

### Features
- Real-time data updates via WebSocket
- Historical data visualization with Recharts
- Transformations: YoY%, MoM%, Moving Averages
- Dashboard buttons (Inflation, Labor, Claims, GDP)
- Search and filter indicators
- Export to Excel
- Risk alerts by severity
