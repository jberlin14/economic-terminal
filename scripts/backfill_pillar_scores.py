"""
One-off backfill: reconstruct `pillar_scores_snapshot` for journal entries
that pre-date Phase 1 §1.4 (when the scorecard began persisting daily
snapshots).

Usage:
    python scripts/backfill_pillar_scores.py             # apply
    python scripts/backfill_pillar_scores.py --dry-run   # preview
    python scripts/backfill_pillar_scores.py --overwrite # re-run for already-reconstructed entries

Skipped categories:
  * Entries that already have a real (live-written) snapshot — never
    overwritten.
  * Entries whose `indicator_snapshot` lacks any usable signal (no CPI
    YoY, sahm rule, 10y2y spread, or credit_stress).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as `python scripts/backfill_pillar_scores.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from modules.data_storage.database import get_db_context
from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run reconstruction for entries that already have a "
             "_reconstructed snapshot. Live snapshots are never overwritten.",
    )
    args = parser.parse_args()

    with get_db_context() as db:
        report = backfill_pillar_scores_snapshot(
            db,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
