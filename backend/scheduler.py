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
        from backend.websocket import broadcast_yield_update

        # Fetch spreads
        fetcher = CreditDataFetcher()
        update = fetcher.fetch_all_spreads()

        if update and update.spreads:
            # Store in database
            store_credit_update(update)

            # Broadcast update to WebSocket clients
            await broadcast_yield_update({
                'type': 'credit_spreads',
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

    except Exception as e:
        logger.error(f"News fetch failed: {e}")
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
                
                # Mark as sent
                alert_ids = [a.id for a in critical]
                manager.mark_email_sent(alert_ids)
            
            # Expire old alerts
            manager.expire_old_alerts(hours=24)
            
    except Exception as e:
        logger.error(f"Alert check failed: {e}")


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

    # Alert check - every minute
    scheduler.add_job(
        check_alerts,
        IntervalTrigger(minutes=1),
        id='alert_check',
        name='Alert Check',
        replace_existing=True
    )
    
    # Daily digest - 7 AM ET
    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=7, minute=0, timezone='America/New_York'),
        id='daily_digest',
        name='Daily Digest',
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
