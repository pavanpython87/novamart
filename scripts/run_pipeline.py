#!/usr/bin/env python
"""Pipeline CLI entry point — the single command the schedule (GitHub
Actions), Docker, and local development all use to run any pipeline mode.

Usage:
    python scripts/run_pipeline.py --mode incremental
    python scripts/run_pipeline.py --mode full-refresh
    python scripts/run_pipeline.py --mode rebuild-marts --scope daily
    python scripts/run_pipeline.py --mode backfill --start-date 2024-01-01 --end-date 2024-06-30
    python scripts/run_pipeline.py --mode export --formats csv excel pdf
    python scripts/run_pipeline.py --mode dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

# Populate os.environ from a local .env file (see .env.example) before any
# downstream module reads WAREHOUSE_BACKEND/BQ_PROJECT_ID/BQ_DATASET via
# os.environ.get(...) — a no-op if no .env file exists (e.g. in CI/Docker,
# where these are set directly in the environment).
load_dotenv()

from src.orchestration.flows.backfill_flow import backfill_flow  # noqa: E402
from src.orchestration.flows.export_flow import export_flow  # noqa: E402
from src.orchestration.flows.full_refresh_flow import full_refresh_flow  # noqa: E402
from src.orchestration.flows.incremental_flow import incremental_flow  # noqa: E402
from src.orchestration.flows.main_pipeline import main_pipeline  # noqa: E402
from src.orchestration.flows.rebuild_marts_flow import rebuild_marts_flow  # noqa: E402

# force=True: importing the Prefect flow modules above already attaches a
# handler to the root logger, which makes basicConfig() a silent no-op
# (and leaves the root level at WARNING) without it — swallowing every
# INFO log this script emits, including the final run summary below.
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                     force=True)
logger = logging.getLogger(__name__)


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["incremental", "full-refresh", "rebuild-marts", "backfill", "export", "dry-run"],
        default="incremental",
        help="Which pipeline mode to run (see PROJECT_PLAN.md 3.2)",
    )
    parser.add_argument("--scope", choices=["daily", "weekly", "all"], default="all",
                         help="Which marts to rebuild (rebuild-marts mode only)")
    parser.add_argument("--start-date", type=_parse_date, help="Backfill range start (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, help="Backfill range end (YYYY-MM-DD)")
    parser.add_argument("--formats", nargs="+", default=["csv", "excel"],
                         choices=["csv", "excel", "pdf"],
                         help="Export formats (export mode only)")
    parser.add_argument("--output-dir", default="data/exports", help="Export directory")
    parser.add_argument("--sources-config", default="config/pipeline_config.yaml")
    parser.add_argument("--seed", type=int, default=42, help="Simulation seed (backfill mode)")
    parser.add_argument("--chaos-level", type=float, default=1.0,
                         help="Chaos-injection multiplier (backfill mode)")

    args = parser.parse_args()
    if args.mode == "backfill" and (not args.start_date or not args.end_date):
        parser.error("--mode backfill requires --start-date and --end-date")
    return args


def main() -> None:
    args = parse_args()

    if args.mode == "incremental":
        result = incremental_flow(sources_config=args.sources_config)
    elif args.mode == "full-refresh":
        result = full_refresh_flow(sources_config=args.sources_config)
    elif args.mode == "rebuild-marts":
        result = rebuild_marts_flow(scope=args.scope, sources_config=args.sources_config)
    elif args.mode == "backfill":
        result = backfill_flow(
            args.start_date, args.end_date,
            sources_config=args.sources_config,
            seed=args.seed, chaos_level=args.chaos_level,
        )
    elif args.mode == "export":
        result = export_flow(export_dir=args.output_dir, formats=tuple(args.formats))
    elif args.mode == "dry-run":
        result = main_pipeline(sources_config=args.sources_config, dry_run=True)
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    logger.info("Pipeline run complete: mode=%s batch_id=%s", args.mode, result.get("batch_id"))
    logger.info("Summary: %s", result)


if __name__ == "__main__":
    main()
