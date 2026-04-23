"""
Background Scheduler

Handles periodic data fetching and updates using APScheduler.
"""

import os
import asyncio
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz
from loguru import logger

# Initialize scheduler
scheduler = AsyncIOScheduler(timezone=pytz.timezone('America/New_York'))


async def update_fx_rates():
    """Fetch and store latest FX rates."""
    logger.info("Scheduled: Updating FX rates...")
    
    try:
        from modules.fx_monitor.data_fetcher import FXDataFetcher
        from modules.fx_monitor.storage import store_fx_update
        from modules.risk_detector.fx_rules import detect_fx_risks
        from modules.risk_detector.alert_manager import AlertManager
        from modules.data_storage.database import get_db_context
        from backend.websocket import broadcast_fx_update, broadcast_alert
        
        # Fetch rates
        fetcher = FXDataFetcher()
        update = await fetcher.fetch_all()
        await fetcher.close()
        
        if update.rates:
            # Store in database
            store_fx_update(update)
            
            # Prepare data for risk detection
            fx_data = {}
            for rate in update.rates:
                fx_data[rate.pair] = {
                    'rate': rate.rate,
                    'change_1h': rate.change_1h,
                    'change_24h': rate.change_24h
                }
            
            # Detect risks
            risks = detect_fx_risks(fx_data)
            
            # Process alerts
            if risks:
                with get_db_context() as db:
                    manager = AlertManager(db)
                    batch = manager.process_alerts(risks, source_module='fx_monitor')
                    
                    # Broadcast critical alerts via WebSocket
                    for alert in batch.alerts:
                        if alert.severity == 'CRITICAL':
                            await broadcast_alert(alert.to_dict())
            
            # Broadcast update to WebSocket clients
            await broadcast_fx_update({
                'rates': [json.loads(r.json()) for r in update.rates],
                'timestamp': update.timestamp.isoformat()
            })
            
            logger.success(f"FX update complete: {len(update.rates)} rates")
        else:
            logger.warning("No FX rates fetched")
            
    except Exception as e:
        logger.error(f"FX update failed: {e}")
        import traceback
        traceback.print_exc()


async def update_yields():
    """Fetch and store latest yield curve."""
    logger.info("Scheduled: Updating yield curve...")
    
    try:
        from modules.yields_monitor.data_fetcher import YieldsDataFetcher
        from modules.yields_monitor.storage import store_yield_curve
        from modules.risk_detector.yield_rules import detect_yield_risks
        from modules.risk_detector.alert_manager import AlertManager
        from modules.data_storage.database import get_db_context
        from backend.websocket import broadcast_yield_update, broadcast_alert
        
        # Fetch curve
        fetcher = YieldsDataFetcher()
        curve = fetcher.fetch_yield_curve()
        
        if curve:
            # Store in database
            store_yield_curve(curve)
            
            # Detect risks
            yield_data = curve.curve_dict
            yield_data['spread_10y2y'] = curve.spread_10y2y
            risks = detect_yield_risks(yield_data)
            
            # Process alerts
            if risks:
                with get_db_context() as db:
                    manager = AlertManager(db)
                    batch = manager.process_alerts(risks, source_module='yields_monitor')
                    
                    for alert in batch.alerts:
                        if alert.severity == 'CRITICAL':
                            await broadcast_alert(alert.to_dict())
            
            # Broadcast update
            await broadcast_yield_update(json.loads(curve.json()))
            
            logger.success("Yield curve update complete")
        else:
            logger.warning("No yield data fetched")
            
    except Exception as e:
        logger.error(f"Yield update failed: {e}")


async def update_credit_spreads():
    """Fetch and store latest credit spreads."""
    logger.info("Scheduled: Updating credit spreads...")

    try:
        from modules.credit_monitor.data_fetcher import CreditDataFetcher
        from modules.credit_monitor.storage import store_credit_update
        from backend.websocket import broadcast_credit_update

        # Fetch spreads
        fetcher = CreditDataFetcher()
        update = fetcher.fetch_all_spreads()

        if update and update.spreads:
            # Store in database
            store_credit_update(update)

            # Broadcast update to WebSocket clients
            await broadcast_credit_update({
                'spreads': [json.loads(s.json()) for s in update.spreads],
                'timestamp': update.timestamp.isoformat()
            })

            logger.success(f"Credit spreads update complete: {len(update.spreads)} indices")
        else:
            logger.warning("No credit spread data fetched")

    except Exception as e:
        logger.error(f"Credit spreads update failed: {e}")
        import traceback
        traceback.print_exc()


async def fetch_news():
    """Fetch news from RSS feeds."""
    logger.info("Scheduled: Fetching news from RSS feeds...")

    try:
        from modules.news_aggregator.rss_fetcher import RSSFetcher
        from modules.news_aggregator.storage import store_news_feed
        from backend.websocket import broadcast_news

        # Fetch all RSS feeds
        fetcher = RSSFetcher()
        feeds = fetcher.fetch_all_feeds(max_articles=10)

        total_stored = 0
        total_duplicates = 0

        for feed in feeds:
            if feed.articles:
                # Store in database with deduplication
                counts = store_news_feed(feed)
                total_stored += counts['stored']
                total_duplicates += counts['duplicates']

                # Broadcast new articles via WebSocket
                for article in feed.articles:
                    if counts['stored'] > 0:  # Only broadcast if we stored new ones
                        await broadcast_news(json.loads(article.json()))

        logger.success(f"News fetch complete: {total_stored} new, {total_duplicates} duplicates")

        # Scrape full text for new articles in background
        if total_stored > 0:
            await scrape_article_texts()

    except Exception as e:
        logger.error(f"News fetch failed: {e}")
        import traceback
        traceback.print_exc()


async def scrape_article_texts():
    """Scrape full article text for recent articles missing full_text."""
    logger.info("Scheduled: Scraping article full texts...")

    try:
        from modules.news_aggregator.article_scraper import scrape_missing_articles

        loop = asyncio.get_running_loop()
        counts = await loop.run_in_executor(None, scrape_missing_articles)

        if counts['scraped'] > 0:
            logger.success(
                f"Article scraping complete: {counts['scraped']} scraped, "
                f"{counts['failed']} failed, {counts['skipped']} skipped"
            )

    except Exception as e:
        logger.error(f"Article scraping failed: {e}")
        import traceback
        traceback.print_exc()


async def check_alerts():
    """Check for new alerts and send emails if needed."""
    logger.debug("Checking for unsent alerts...")
    
    try:
        from modules.risk_detector.alert_manager import AlertManager
        from modules.data_storage.database import get_db_context
        
        with get_db_context() as db:
            manager = AlertManager(db)
            
            # Get unsent alerts
            alerts = manager.get_alerts_for_email(unsent_only=True)
            
            critical = alerts.get('critical', [])
            if critical:
                logger.warning(f"Found {len(critical)} unsent CRITICAL alerts")
                # TODO: Send immediate email via email_reporter module
                # Alerts are NOT marked as sent until email sending is implemented,
                # so they will continue to appear in unsent queries.
            
            # Expire old alerts
            manager.expire_old_alerts(hours=24)
            
    except Exception as e:
        logger.error(f"Alert check failed: {e}")


async def update_indicators():
    """
    Update economic indicators with latest data from FRED.
    Runs Monday-Friday at 8:30 AM ET (after economic releases).
    Fetches recent data (last 90 days) to catch new releases and revisions.
    """
    logger.info("Scheduled: Updating economic indicators from FRED...")

    try:
        from modules.economic_indicators import IndicatorDataFetcher, IndicatorStorage
        from modules.data_storage.database import get_db_context
        from datetime import datetime as dt, timedelta

        fetcher = IndicatorDataFetcher()

        if not fetcher.is_available():
            logger.warning("FRED API not available, skipping indicator update")
            return

        updated_series = 0
        new_data_points = 0
        revised_points = 0
        errors = []

        # Always look back 90 days to catch new releases + revisions
        lookback_start = (dt.now() - timedelta(days=90)).strftime('%Y-%m-%d')

        with get_db_context() as db:
            storage = IndicatorStorage(db)

            # Get all indicators
            indicators = storage.get_all_indicators()

            for indicator in indicators:
                try:
                    df = fetcher.fetch_series(
                        indicator.series_id,
                        start_date=lookback_start,
                    )

                    if df is not None and not df.empty:
                        # Store new values + update revised values
                        stored, revised = storage.store_values(indicator.series_id, df, update_revised=True)

                        if stored > 0 or revised > 0:
                            updated_series += 1
                            new_data_points += stored
                            revised_points += revised
                            logger.debug(f"  {indicator.series_id}: +{stored} new, {revised} revised")

                except Exception as e:
                    errors.append(indicator.series_id)
                    logger.error(f"  {indicator.series_id}: {e}")

        parts = []
        if new_data_points:
            parts.append(f"{new_data_points} new")
        if revised_points:
            parts.append(f"{revised_points} revised")
        if parts:
            logger.success(f"Indicators update complete: {updated_series} series, {', '.join(parts)} data points")
        else:
            logger.info("Indicators update complete: No new data available")

        if errors:
            logger.warning(f"Failed to update {len(errors)} series: {', '.join(errors[:5])}")

    except Exception as e:
        logger.error(f"Indicator update failed: {e}")
        import traceback
        traceback.print_exc()


async def update_market_indices():
    """Fetch and store latest market indices (VIX, oil, gold, S&P 500)."""
    from modules.market_indices import update_market_indices as _update
    await _update()


async def generate_daily_journal():
    """Generate the daily AI market journal entry with pre-computed analytics."""
    logger.info("Scheduled: Generating daily market journal...")

    try:
        from modules.market_summary.journal import MarketJournal
        from modules.data_storage.database import get_db_context

        with get_db_context() as db:
            journal = MarketJournal(db)
            entry = journal.create_or_update_today()
            if entry:
                themes = ", ".join(entry.key_themes or [])
                logger.success(
                    f"Daily journal created: {entry.date} | "
                    f"Regime: {entry.regime} | Themes: {themes}"
                )
            else:
                logger.warning("Failed to create daily journal entry")

    except Exception as e:
        logger.error(f"Daily journal generation failed: {e}")
        import traceback
        traceback.print_exc()


async def send_daily_digest():
    """Send daily market digest email."""
    logger.info("Sending daily digest...")

    try:
        # TODO: Implement daily digest email
        # from modules.email_reporter.digest_generator import generate_daily_digest
        # await generate_daily_digest()
        logger.info("Daily digest sent (placeholder)")

    except Exception as e:
        logger.error(f"Daily digest failed: {e}")


async def cleanup_old_data():
    """Clean up old data from database."""
    logger.info("Running data cleanup...")
    
    try:
        from modules.data_storage.database import get_db_context
        from modules.data_storage.queries import QueryHelper
        
        with get_db_context() as db:
            helper = QueryHelper(db)
            counts = helper.cleanup_old_data(days=90)
            logger.info(f"Cleaned up: {counts}")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


def start_scheduler():
    """Start the background scheduler with all jobs."""
    
    # FX rates - every 5 minutes
    scheduler.add_job(
        update_fx_rates,
        IntervalTrigger(minutes=5),
        id='fx_update',
        name='FX Rate Update',
        replace_existing=True
    )
    
    # Yield curve - every 5 minutes
    scheduler.add_job(
        update_yields,
        IntervalTrigger(minutes=5),
        id='yield_update',
        name='Yield Curve Update',
        replace_existing=True
    )

    # Market indices (VIX, oil, gold, S&P 500) - every 5 minutes
    scheduler.add_job(
        update_market_indices,
        IntervalTrigger(minutes=5),
        id='market_index_update',
        name='Market Index Update',
        replace_existing=True
    )

    # Credit spreads - every 30 minutes
    scheduler.add_job(
        update_credit_spreads,
        IntervalTrigger(minutes=30),
        id='credit_update',
        name='Credit Spreads Update',
        replace_existing=True
    )

    # News feed - every 15 minutes
    scheduler.add_job(
        fetch_news,
        IntervalTrigger(minutes=15),
        id='news_fetch',
        name='News Feed Fetch',
        replace_existing=True
    )

    # Article full-text scraping - every 30 minutes (catches missed articles)
    scheduler.add_job(
        scrape_article_texts,
        IntervalTrigger(minutes=30),
        id='article_scrape',
        name='Article Full-Text Scrape',
        replace_existing=True
    )

    # Alert check - every minute
    scheduler.add_job(
        check_alerts,
        IntervalTrigger(minutes=1),
        id='alert_check',
        name='Alert Check',
        replace_existing=True
    )
    
    # Daily market journal - 7:00 AM ET every day (including weekends for continuous timeline)
    scheduler.add_job(
        generate_daily_journal,
        CronTrigger(hour=7, minute=0, timezone='America/New_York'),
        id='daily_journal',
        name='Daily Market Journal',
        replace_existing=True
    )

    # Daily digest - 7:15 AM ET (after journal is generated)
    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=7, minute=15, timezone='America/New_York'),
        id='daily_digest',
        name='Daily Digest',
        replace_existing=True
    )
    
    # Economic indicators - daily at 8:30 AM ET, Monday-Friday
    scheduler.add_job(
        update_indicators,
        CronTrigger(hour=8, minute=30, day_of_week='mon-fri', timezone='America/New_York'),
        id='indicator_update',
        name='Economic Indicators Update',
        replace_existing=True
    )

    # Data cleanup - daily at 3 AM ET
    scheduler.add_job(
        cleanup_old_data,
        CronTrigger(hour=3, minute=0, timezone='America/New_York'),
        id='data_cleanup',
        name='Data Cleanup',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}: {job.trigger}")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status():
    """Get current scheduler status."""
    return {
        'running': scheduler.running,
        'jobs': [
            {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ]
    }
