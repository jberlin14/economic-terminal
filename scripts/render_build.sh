#!/usr/bin/env bash
#
# Render Build Script
# Runs on Render.com during deployment
#

set -e  # Exit on error

echo "========================================="
echo "Economic Terminal - Render Build"
echo "========================================="

# Install Python dependencies
echo "[1/4] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
echo "[2/4] Initializing database..."
if [ ! -f "/data/economic_data.db" ]; then
    echo "  Creating new database..."
    python scripts/init_db.py
else
    echo "  Database already exists, checking schema..."
    python scripts/migrate_database.py || true
fi

# Initialize economic indicators (if not already done)
echo "[3/4] Checking economic indicators..."
python -c "
from modules.data_storage.database import get_db_context
from modules.economic_indicators.storage import IndicatorStorage

with get_db_context() as db:
    storage = IndicatorStorage(db)
    count = len(storage.get_all_indicators())
    print(f'  Found {count} indicators in database')

    if count == 0:
        print('  No indicators found, will initialize on first run')
        print('  Run: python scripts/init_indicators.py after deployment')
" || true

# Health check
echo "[4/4] Running health check..."
python scripts/health_check.py || true

echo "========================================="
echo "Build complete!"
echo "========================================="
