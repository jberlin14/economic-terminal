# Economic Terminal - Project Context

## What This Is
A full-stack AI-powered economic intelligence terminal. Tracks macro indicators, FX, yields, credit spreads, and news — then uses AI to generate narratives, detect regime shifts, match historical playbooks, and track cross-asset correlations. Built for enterprise risk management.

## Tech Stack
- **Backend:** Python FastAPI, SQLAlchemy ORM, SQLite (local) / PostgreSQL (prod), APScheduler
- **Frontend:** React 18 + TypeScript, Tailwind CSS (dark terminal theme), Recharts, Lucide icons
- **AI:** Anthropic Claude API (`claude-sonnet-4-5-20250929`) for narratives and chat
- **Data Sources:** FRED API (79+ economic indicators), Alpha Vantage (FX), yfinance (equities/VIX), 27+ RSS feeds (news)

## Running the App
```bash
# Backend (from repo root)
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm start
```
Environment variables in `.env`: `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `ANTHROPIC_API_KEY`

## Project Structure

### Backend (`backend/`)
- `main.py` — FastAPI app, CORS, router registration, startup/shutdown
- `scheduler.py` — APScheduler cron/interval jobs (FX every 5m, yields every 5m, news every 15m, indicators at 8:30 AM ET, daily journal at 7 AM ET)
- `websocket.py` — WebSocket broadcast for real-time updates
- `api/` — Route modules:
  - `health.py` — Health check, `/api/refresh` (triggers all data source updates)
  - `indicators.py` — CRUD + history + transforms + dashboards for economic indicators
  - `fx.py`, `yields.py`, `credit.py` — Market data endpoints
  - `news.py`, `news_advanced.py` — News feed with categorization, severity, leader detection
  - `calendar.py` — Economic release calendar (uses FRED release dates API)
  - `intelligence.py` — Regime detection, playbook matching, correlation tracking
  - `risks.py` — Alert management

### Frontend (`frontend/src/`)
- **Pages:** `Dashboard.tsx` (main), `HistoricalData.tsx` (indicator charts), `Calendar.tsx` (release schedule)
- **Key Components:** `ChatInterface.tsx` (floating AI chat), `IntelligencePanel.tsx` (regime/playbook/correlations tabs), `MarketNarrative.tsx` (AI-generated daily narrative), `NewsFeed.tsx`, `FXDashboard.tsx`, `YieldCurveChart.tsx`, `CreditSpreadsPanel.tsx`, `TreasuryHistoryTable.tsx`
- **Routing:** React Router in `App.tsx`, nav in `Header.tsx`

### Modules (`modules/`)

#### Data Layer
- `data_storage/schema.py` — All SQLAlchemy models (NewsArticle, FXRate, YieldCurve, CreditSpread, EconomicIndicator, IndicatorValue, EconomicRelease, RiskAlert, AIMarketJournal, etc.)
- `data_storage/database.py` — DB engine, session factory, `get_db_context()` context manager

#### Economic Indicators (`economic_indicators/`)
- `config.py` — 79 FRED series definitions organized by report group (CPI, PPI, Employment, GDP, Housing, etc.)
- `data_fetcher.py` — FRED API client with rate limiting (120 req/min)
- `storage.py` — `IndicatorStorage` class: CRUD, transforms, comparison data, lookback-aware fetching for YoY/MoM
- `transformer.py` — `DataTransformer`: date-based YoY/MoM calculations (handles data gaps correctly), moving averages, annualized rates

#### Market Intelligence
- `market_summary/ai_narrative.py` — `AIMarketNarrative` (1,686 lines): gathers all market data, computes analytics (trends, z-scores, derived metrics, regime classification), generates AI narrative via Claude API
- `market_summary/analytics_engine.py` — Shared analytics utility that delegates to AIMarketNarrative's methods. Used by both narrative generator and chat engine
- `market_summary/journal.py` — `MarketJournal`: persistent daily market assessments stored in `ai_market_journal` table
- `market_summary/change_detector.py` — Diffs current snapshot vs prior journal entry, surfaces material moves

#### AI Chat (`conversational_ai/`)
- `chat_engine.py` — `ChatEngine`: stateful conversation manager with pre-computed market context. Builds analytics-powered snapshot (regime, trends, derived metrics, change detection, journal history) for each AI call

#### Intelligence Modules
- `regime_detector/` — Monitors yield curve, credit spreads, VIX, FX for regime shifts (RISK_ON → CAUTIOUS → RISK_OFF → CRISIS)
- `playbook_matcher/` — Matches current conditions against historical episodes (2008 GFC, 2020 COVID, etc.)
- `correlation_tracker/` — Tracks cross-asset correlation breakdowns (stocks/bonds, USD/gold, etc.)

#### Market Data
- `fx_monitor/` — FX rate fetching (Alpha Vantage), storage, risk detection
- `yields_monitor/` — Treasury yield curve fetching, spread calculations
- `credit_monitor/` — Credit spread monitoring (IG/HY)
- `news_aggregator/` — RSS fetcher (27+ feeds), categorization, severity scoring, leader/institution detection, storage with deduplication
- `economic_calendar/` — Release scheduling using FRED release dates API with weekend-skipping fallback

## Key Patterns

### Data Flow
1. **Scheduler** triggers periodic fetches → stores in SQLite via SQLAlchemy
2. **API endpoints** read from DB, apply transforms, return JSON
3. **Frontend** fetches via REST, receives real-time updates via WebSocket
4. **AI features** consume pre-computed analytics from `analytics_engine.py`

### Analytics Pipeline
`gather_market_context(db)` → `compute_analytics(context)` → used by:
- `AIMarketNarrative` for daily narrative generation
- `ChatEngine` for AI chat context
- `MarketJournal` for persistent daily snapshots
- `change_detector` for cross-day comparison

### Indicator Transforms
The `DataTransformer` uses **date-based matching** (not row offsets) for YoY/MoM — correctly handles gaps in time series data. When requesting transformed data, `IndicatorStorage` automatically fetches extra lookback data before the start date to ensure transforms have values from day one.

### Database
- SQLite locally (`data/economic_terminal.db`), PostgreSQL in production
- All models in `modules/data_storage/schema.py`
- Context manager pattern: `with get_db_context() as db:`
- FastAPI dependency: `db: Session = Depends(get_db)`

## Important Notes
- Always load dotenv before using FRED/Anthropic APIs: `from dotenv import load_dotenv; load_dotenv()`
- The backend `main.py` handles dotenv loading at startup
- FRED frequently revises economic data — `store_values(df, update_revised=True)` handles this
- News articles have `headline`, `summary` (500 chars from RSS), and `full_text` (column exists but not yet populated — web scraping TODO)
- The `ai_narrative.py` file is large (1,686 lines) — analytics methods are accessed via `analytics_engine.py` to avoid importing the full class

---

## Recent Changes (Feb 14–15, 2026)

### New Features Built

#### 1. Macro Risk Scorecard (`modules/risk_scorecard/`, `frontend/src/pages/RiskScorecard.tsx`)
- 6-pillar weighted scoring system: Yield Curve (20%), Credit (20%), Volatility (15%), Inflation (15%), Labor (15%), Geopolitical (15%)
- Geopolitical pillar uses market-derived signals (oil, gold, EM FX) not news severity labels
- Per-pillar methodology panel with expandable "How it's scored" sections
- Horizontal score bars, colored icon boxes, responsive layout

#### 2. Regime Timeline (`frontend/src/pages/RegimeTimeline.tsx`, `modules/regime_detector/`)
- Visual timeline of regime shifts (RISK_ON → CAUTIOUS → RISK_OFF → CRISIS) over time
- Uses journal snapshots with on-the-fly recomputation via `_recompute_regime_from_snapshot()` in `backend/api/intelligence.py`
- Displays themes (inflation, labor, yield curve, credit, policy stance) per entry with narrative summaries

#### 3. Scenario Simulator (`modules/scenario_simulator/`, `frontend/src/pages/ScenarioSimulator.tsx`)
- AI-powered "what if" scenario analysis using Claude API
- Robust JSON parsing with field name normalization and guaranteed consistent output structure
- Visual cascade timeline with numbered circles, gradient connectors, timeframe pills
- Impact cards with colored borders (green/red) and confidence meters
- All 5 sections always render with empty state placeholders for consistency

#### 4. AI Chat Interface (`modules/conversational_ai/chat_engine.py`, `frontend/src/components/ChatInterface.tsx`)
- Floating chat widget with stateful conversation manager
- Pre-computed market context (regime, trends, derived metrics, change detection, journal history) injected into each AI call

#### 5. Intelligence Panel (`frontend/src/components/IntelligencePanel.tsx`)
- Unified 5-tab panel: Regime, Playbooks, Correlations, Theory Library, Scenario Sim
- Integrates regime detector, playbook matcher, correlation tracker

#### 6. Market Journal (`modules/market_summary/journal.py`)
- Persistent daily market assessments stored in `ai_market_journal` table
- Rule-based `_build_narrative_summary()` covering regime, inflation, labor, yield curve, credit, policy stance
- Theme extraction from snapshot data (inflation level, labor via Sahm rule, curve shape via 10Y-2Y spread)

#### 7. Supporting Modules
- `modules/playbook_matcher/` — Matches current conditions against historical episodes (2008 GFC, 2020 COVID, etc.)
- `modules/correlation_tracker/` — Tracks cross-asset correlation breakdowns (stocks/bonds, USD/gold, etc.)
- `modules/theory_library/` — Reference library of macro-economic theories
- `modules/market_summary/change_detector.py` — Diffs current snapshot vs prior journal entry
- `modules/market_summary/analytics_engine.py` — Shared analytics utility for narrative + chat

### Bug Fixes & Accuracy Corrections

#### Yield Curve Shape Classification (`modules/risk_detector/yield_rules.py`)
- **Bug:** Old code counted ALL consecutive inversions (including minor front-end kinks like 1M>3M). 3+ inversions = DEEPLY_INVERTED even with positive 10Y-2Y spread.
- **Fix:** Uses 10Y-2Y spread as primary classifier (STEEP >100bps, NORMAL >25bps, FLAT -10 to +25bps, PARTIALLY_INVERTED <-10bps, DEEPLY_INVERTED <-50bps). Only counts key-segment inversions (2Y→5Y, 5Y→10Y, 2Y→10Y, 3M→2Y, 3M→10Y) as secondary signal.

#### Market Regime Assessment (`modules/market_summary/ai_narrative.py` `_compute_market_regime`)
- **Bug:** Simple signal counting — 1 signal = CAUTIOUS regardless of severity.
- **Fix:** Weighted scoring system with severity weights per signal type. Thresholds: RISK_ON (<2.0), CAUTIOUS (2.0–3.5), RISK_OFF (3.5–5.0), CRISIS (≥5.0). Added VIX as supplemental signal.

#### CPI Trend Accuracy (`modules/risk_scorecard/scorecard.py`)
- **Bug:** Analytics engine computed CPI trend from raw index MA slope (always positive/ACCELERATING since CPI index always rises).
- **Fix:** Scorecard uses CPI MoM momentum (>0.3% = accelerating, <0.2% = decelerating) with YoY level fallback (<2.5% → improving).

#### Labor Theme in Timeline Recomputation (`backend/api/intelligence.py`)
- **Bug:** `sahm < 0.30` condition meant sahm=0.30 fell to else → "labor_softening". Inconsistent with journal.py which uses `sahm > 0.3`.
- **Fix:** Reordered conditions — `sahm_triggered` first, then `sahm > 0.30` for softening, else stable. Now sahm=0.30 correctly → "labor_stable".

#### Journal Theme Extraction (`modules/market_summary/journal.py`)
- **Bug:** `_extract_themes` checked stored `curve_shape` string (which was stale/buggy).
- **Fix:** Changed to use 10Y-2Y spread directly for yield curve theme classification.

### UI/UX Improvements

#### Mobile Responsiveness (`frontend/src/components/Header.tsx`)
- Added hamburger menu (`Menu`/`X` icons) visible on screens < `lg` breakpoint
- Mobile nav drawer as 2-column grid, auto-closes on link click
- Responsive sizing with `sm:`, `lg:`, `xl:` breakpoints throughout

#### AI Writing Style (narrative_modes.py, chat_engine.py, simulator.py)
- Added mandatory writing style rules to all AI system prompts: no em-dashes, no triple-clause sentences, no AI-isms ("notably", "signaling"), Goldman morning note style

### Key Technical Decisions
- **Regime recomputation on read:** Timeline endpoint recomputes regime from stored `indicator_snapshot` data using corrected logic, so old entries with buggy classifications are fixed on-the-fly without needing data migration
- **Market-derived geopolitical risk:** Uses oil prices, gold, and EM FX spreads instead of subjective news severity labels — more quantitative and reproducible
- **Consistent scenario output:** Backend `_parse_response` guarantees all fields exist via normalization; frontend always renders all 5 sections with empty state placeholders
