"""
Economic Indicators API Endpoints

Provides access to historical economic indicator data with transformations.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
import math

from modules.data_storage.database import get_db
from modules.data_storage.schema import EconomicIndicator
from modules.economic_indicators import (
    IndicatorStorage,
    DataTransformer,
    IndicatorDataFetcher,
    ExcelExporter,
    REPORT_GROUPS,
    DASHBOARDS,
    get_all_indicators,
    fetch_and_store_all_indicators
)

router = APIRouter()


# ==================== Metadata & Search ====================

@router.get("/")
async def get_all_indicators_grouped(db: Session = Depends(get_db)):
    """
    Get all indicators grouped by report_group.
    Only includes indicators that have data in the database.

    Returns:
        {
            "Employment Situation": [{series_id, name, units, ...}, ...],
            "CPI Report": [...],
            ...
        }
    """
    storage = IndicatorStorage(db)
    all_indicators = storage.get_all_indicators()

    # Group by report_group, only include indicators with data
    grouped = {}
    for indicator in all_indicators:
        # Check if indicator has any data
        if storage.get_value_count(indicator.series_id) > 0:
            report_group = indicator.report_group
            if report_group not in grouped:
                grouped[report_group] = []
            grouped[report_group].append(indicator.to_dict())

    return grouped


@router.get("/search")
async def search_indicators(
    q: str = Query(..., description="Search query for name or series ID"),
    db: Session = Depends(get_db)
):
    """
    Search indicators by name or series_id.

    Args:
        q: Search query string

    Returns:
        List of matching indicators
    """
    storage = IndicatorStorage(db)
    results = storage.search_indicators(q)
    return [ind.to_dict() for ind in results]


@router.get("/reports")
async def get_report_groups(db: Session = Depends(get_db)):
    """
    Get list of report groups with indicator counts.

    Returns:
        [
            {"name": "Employment Situation", "count": 30},
            {"name": "CPI Report", "count": 18},
            ...
        ]
    """
    storage = IndicatorStorage(db)
    all_indicators = storage.get_all_indicators()

    # Count by report group
    counts = {}
    for indicator in all_indicators:
        report_group = indicator.report_group
        counts[report_group] = counts.get(report_group, 0) + 1

    return [{"name": name, "count": count} for name, count in counts.items()]


@router.get("/report/{report_name}")
async def get_report_indicators(
    report_name: str,
    db: Session = Depends(get_db)
):
    """
    Get all indicators for a specific report group.

    Args:
        report_name: Report group name (e.g., 'CPI Report')

    Returns:
        List of indicators in that report
    """
    storage = IndicatorStorage(db)
    indicators = storage.get_indicators_by_report(report_name)

    if not indicators:
        raise HTTPException(status_code=404, detail=f"Report group '{report_name}' not found")

    return [ind.to_dict() for ind in indicators]


# ==================== Comparison ====================

@router.get("/compare")
async def compare_indicators(
    series: str = Query(..., description="Comma-separated series IDs"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    transform: Optional[str] = Query(None, description="Transform to apply to all series"),
    db: Session = Depends(get_db)
):
    """
    Compare multiple indicators on the same date index.

    Args:
        series: Comma-separated series IDs (e.g., "PAYEMS,UNRATE,CES0500000003")
        start: Start date
        end: End date
        transform: Optional transformation to apply

    Returns:
        {
            "series": [
                {"series_id": "PAYEMS", "name": "Total Nonfarm", "units": "thousands"},
                {"series_id": "UNRATE", "name": "Unemployment Rate", "units": "percent"}
            ],
            "data": [
                {"date": "2024-01-01", "PAYEMS": 158000, "UNRATE": 3.7},
                {"date": "2024-02-01", "PAYEMS": 158256, "UNRATE": 3.8},
                ...
            ]
        }
    """
    storage = IndicatorStorage(db)

    # Parse series IDs
    series_ids = [s.strip() for s in series.split(',')]

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    # Get metadata for all series
    series_info = []
    missing_series = []
    for series_id in series_ids:
        indicator = storage.get_indicator(series_id)
        if indicator:
            series_info.append({
                "series_id": indicator.series_id,
                "name": indicator.name,
                "units": indicator.units,
                "frequency": indicator.frequency
            })
        else:
            missing_series.append(series_id)

    if not series_info:
        raise HTTPException(
            status_code=404,
            detail=f"Series not found: {', '.join(missing_series)}"
        )

    # Get comparison data only for valid series
    valid_series_ids = [s['series_id'] for s in series_info]
    df = storage.get_comparison_data(valid_series_ids, start_date, end_date, transform)

    if df.empty:
        error_msg = "No data available for specified series and date range"
        if missing_series:
            error_msg += f" (Missing series: {', '.join(missing_series)})"
        raise HTTPException(status_code=404, detail=error_msg)

    # Convert to records
    df_reset = df.reset_index()
    data = df_reset.to_dict(orient='records')

    # Convert date objects to strings and handle NaN values
    for row in data:
        if 'date' in row and isinstance(row['date'], date):
            row['date'] = row['date'].isoformat()
        # Replace NaN/Infinity with None for JSON serialization
        for key, value in row.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    row[key] = None

    return {
        "series": series_info,
        "data": data
    }


# ==================== Single Series ====================

@router.get("/{series_id}")
async def get_indicator_info(
    series_id: str,
    db: Session = Depends(get_db)
):
    """
    Get indicator metadata with latest value and basic changes.

    Returns:
        {
            "series_id": "PAYEMS",
            "name": "Total Nonfarm",
            "units": "thousands",
            "frequency": "monthly",
            "latest": {
                "date": "2025-01-01",
                "value": 159234,
                "mom_change": 256,
                "mom_percent": 0.16,
                "yoy_change": 2145,
                "yoy_percent": 1.37
            },
            "data_range": {
                "start_date": "2015-01-01",
                "end_date": "2025-01-01",
                "count": 120
            }
        }
    """
    storage = IndicatorStorage(db)
    transformer = DataTransformer()

    indicator = storage.get_indicator(series_id)
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{series_id}' not found")

    # Get latest value with changes
    df = storage.get_values(series_id)
    latest_with_changes = None
    if not df.empty:
        latest_with_changes = transformer.get_latest_with_changes(df, indicator.frequency)

    # Get data range
    data_range = storage.get_date_range(series_id)
    if data_range:
        # Convert date objects to strings for JSON serialization
        data_range = {
            'start_date': data_range['start_date'].isoformat(),
            'end_date': data_range['end_date'].isoformat(),
            'count': storage.get_value_count(series_id)
        }

    return {
        **indicator.to_dict(),
        "latest": latest_with_changes,
        "data_range": data_range
    }


@router.get("/{series_id}/history")
async def get_indicator_history(
    series_id: str,
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    transform: Optional[str] = Query('raw', description="Transform: raw|mom_change|mom_percent|yoy_change|yoy_percent"),
    ma: Optional[str] = Query(None, description="Moving averages (comma-separated periods, e.g., 3,6,12)"),
    db: Session = Depends(get_db)
):
    """
    Get historical data for a series with optional transformations.

    Args:
        series_id: FRED series ID
        start: Start date
        end: End date
        transform: Transformation to apply
        ma: Comma-separated moving average periods

    Returns:
        {
            "series_id": "PAYEMS",
            "name": "Total Nonfarm",
            "units": "thousands",
            "frequency": "monthly",
            "data": [
                {"date": "2024-01-01", "value": 158000, "mom_percent": 0.25, ...},
                ...
            ]
        }
    """
    storage = IndicatorStorage(db)

    indicator = storage.get_indicator(series_id)
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{series_id}' not found")

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    # Build transformations list
    transformations = []
    if transform and transform != 'raw':
        transformations.append(transform)

    if ma:
        for period in ma.split(','):
            try:
                period_int = int(period.strip())
                transformations.append(f'ma_{period_int}')
            except ValueError:
                pass

    # Get data
    if transformations:
        df = storage.get_values_with_transforms(series_id, start_date, end_date, transformations)
    else:
        df = storage.get_values(series_id, start_date, end_date)

    if df.empty:
        raise HTTPException(status_code=404, detail="No data available for specified date range")

    # Convert to dict format
    data = df.to_dict(orient='records')
    # Convert date objects to strings and handle NaN values
    for row in data:
        if 'date' in row and isinstance(row['date'], date):
            row['date'] = row['date'].isoformat()
        # Replace NaN/Infinity with None for JSON serialization
        for key, value in row.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    row[key] = None

    return {
        "series_id": indicator.series_id,
        "name": indicator.name,
        "units": indicator.units,
        "frequency": indicator.frequency,
        "data": data
    }

# ==================== Pre-configured Dashboards ====================

@router.get("/dashboards")
async def get_dashboards():
    """
    Get list of available pre-configured dashboards.

    Returns:
        [
            {"name": "inflation", "title": "Inflation Dashboard", "series_count": 6},
            ...
        ]
    """
    return [
        {
            "name": name,
            "title": config['name'],
            "series_count": len(config['series']),
            "default_transform": config.get('default_transform', 'raw')
        }
        for name, config in DASHBOARDS.items()
    ]


@router.get("/dashboard/{dashboard_name}")
async def get_dashboard_data(
    dashboard_name: str,
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get data for a pre-configured dashboard.

    Args:
        dashboard_name: Dashboard name ('inflation', 'labor', 'claims', 'gdp')
        start: Start date
        end: End date

    Returns:
        {
            "name": "Inflation Dashboard",
            "series": [...],
            "data": [...]
        }
    """
    if dashboard_name not in DASHBOARDS:
        raise HTTPException(status_code=404, detail=f"Dashboard '{dashboard_name}' not found")

    dashboard_config = DASHBOARDS[dashboard_name]
    series_ids = dashboard_config['series']
    default_transform = dashboard_config.get('default_transform', 'raw')

    storage = IndicatorStorage(db)

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    # Get series metadata
    series_info = []
    for series_id in series_ids:
        indicator = storage.get_indicator(series_id)
        if indicator:
            series_info.append({
                "series_id": indicator.series_id,
                "name": indicator.name,
                "units": indicator.units,
                "frequency": indicator.frequency
            })

    # Get data with default transform
    transform = None if default_transform == 'raw' else default_transform
    df = storage.get_comparison_data(series_ids, start_date, end_date, transform)

    if df.empty:
        return {
            "name": dashboard_config['name'],
            "series": series_info,
            "data": []
        }

    # Convert to records
    df_reset = df.reset_index()
    data = df_reset.to_dict(orient='records')

    # Convert date objects to strings and handle NaN values
    for row in data:
        if 'date' in row and isinstance(row['date'], date):
            row['date'] = row['date'].isoformat()
        # Replace NaN/Infinity with None for JSON serialization
        for key, value in row.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    row[key] = None

    return {
        "name": dashboard_config['name'],
        "default_transform": default_transform,
        "series": series_info,
        "data": data
    }


# ==================== Excel Export ====================

@router.get("/export/excel")
async def export_to_excel(
    series: str = Query(..., description="Comma-separated series IDs"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    transforms: Optional[str] = Query(None, description="Comma-separated transformations"),
    format: str = Query('separate_sheets', description="Format: separate_sheets|columns")
):
    """
    Export indicators to Excel file.

    Args:
        series: Comma-separated series IDs
        start: Start date
        end: End date
        transforms: Comma-separated transformations (for single series only)
        format: Export format

    Returns:
        Excel file download
    """
    exporter = ExcelExporter()

    # Parse series IDs
    series_ids = [s.strip() for s in series.split(',')]

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    # Parse transformations
    transformation_list = []
    if transforms:
        transformation_list = [t.strip() for t in transforms.split(',')]

    try:
        if len(series_ids) == 1 and transformation_list:
            # Single series with transformations
            excel_bytes = exporter.export_single_series(
                series_ids[0],
                start_date,
                end_date,
                transformation_list
            )
            filename = f"{series_ids[0]}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        else:
            # Multiple series
            excel_bytes = exporter.export_multiple_series(
                series_ids,
                start_date,
                end_date,
                format=format
            )
            filename = f"indicators_{datetime.now().strftime('%Y%m%d')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/export/excel/report/{report_name}")
async def export_report_to_excel(
    report_name: str,
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """
    Export entire report group to Excel.

    Args:
        report_name: Report group name
        start: Start date
        end: End date

    Returns:
        Excel file download
    """
    exporter = ExcelExporter()

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    try:
        excel_bytes = exporter.export_report_group(report_name, start_date, end_date)
        filename = f"{report_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/export/excel/dashboard/{dashboard_name}")
async def export_dashboard_to_excel(
    dashboard_name: str,
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """
    Export pre-configured dashboard to Excel.

    Args:
        dashboard_name: Dashboard name
        start: Start date
        end: End date

    Returns:
        Excel file download
    """
    exporter = ExcelExporter()

    # Parse dates
    start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_date = datetime.strptime(end, '%Y-%m-%d').date() if end else None

    try:
        excel_bytes = exporter.export_dashboard(dashboard_name, start_date, end_date)
        filename = f"{dashboard_name}_dashboard_{datetime.now().strftime('%Y%m%d')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Manual Refresh ====================

@router.post("/refresh")
async def refresh_all_indicators():
    """
    Trigger manual refresh of all indicators from FRED.
    This is a long-running operation (5-10 minutes for all 79 indicators).

    Returns:
        {
            "status": "started",
            "message": "Refresh initiated for 79 indicators"
        }
    """
    # This would ideally be run as a background task
    # For now, return a message indicating it should be run via script
    all_indicators = get_all_indicators()

    return {
        "status": "info",
        "message": f"To refresh all {len(all_indicators)} indicators, run: python scripts/fetch_indicators.py",
        "note": "This endpoint will trigger background refresh in a future update"
    }


@router.post("/{series_id}/refresh")
async def refresh_single_indicator(
    series_id: str,
    years_back: int = Query(1, description="Years of history to fetch"),
    db: Session = Depends(get_db)
):
    """
    Refresh a single indicator from FRED.

    Args:
        series_id: FRED series ID
        years_back: Years of history to fetch

    Returns:
        {
            "series_id": "PAYEMS",
            "fetched": 12,
            "stored": 1,
            "status": "success"
        }
    """
    storage = IndicatorStorage(db)
    fetcher = IndicatorDataFetcher()

    if not fetcher.is_available():
        raise HTTPException(status_code=503, detail="FRED API not available")

    indicator = storage.get_indicator(series_id)
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{series_id}' not found")

    try:
        # Fetch data
        df = fetcher.fetch_series(series_id, years_back=years_back)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data available from FRED for {series_id}")

        # Store data
        stored_count = storage.store_values(series_id, df)

        return {
            "series_id": series_id,
            "fetched": len(df),
            "stored": stored_count,
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")
