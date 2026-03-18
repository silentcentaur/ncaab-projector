"""
pipeline/backfill_seasons.py
=============================
Backfills historical NCAAB data from 2015 to the current season.

Run from project root:
  python pipeline/backfill_seasons.py                        # full backfill 2015-2025
  python pipeline/backfill_seasons.py --start 2020           # from 2020 onwards
  python pipeline/backfill_seasons.py --season 2022          # single season only
  python pipeline/backfill_seasons.py --stats-only           # team stats only, no ESPN
  python pipeline/backfill_seasons.py --start 2020 --skip-four-factors  # games but no adv

WARNING: Full backfill (2015-2025) will take 2-3 hours due to ESPN rate limiting.
         Run overnight or use --stats-only first to get team stats quickly.

Tip: Run --stats-only first to populate all seasons in ~5 minutes,
     then run the full backfill overnight for game history + four factors.
"""

import os, sys, time, logging, argparse
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

from fetch_and_store import (
    get_supabase,
    fetch_and_store_team_stats,
    fetch_and_store_game_history,
    fetch_and_store_four_factors,
)

BACKFILL_START = 2015
BACKFILL_END   = 2025  # don't include current season (2026) — handled by nightly


def backfill(start: int, end: int, stats_only: bool, skip_games: bool,
             skip_four_factors: bool):
    sb = get_supabase()
    seasons = list(range(start, end + 1))
    log.info(f"=== Backfill starting: seasons {start}–{end} ({len(seasons)} seasons) ===")
    if stats_only:
        log.info("    Mode: team stats only")
    elif skip_games:
        log.info("    Mode: four factors only (skipping game history)")
    elif skip_four_factors:
        log.info("    Mode: team stats + game history (skipping four factors)")
    else:
        log.info("    Mode: full (team stats + game history + four factors)")

    for i, season in enumerate(seasons):
        log.info(f"\n{'='*60}")
        log.info(f"  Season {season}  ({i+1}/{len(seasons)})")
        log.info(f"{'='*60}")

        try:
            fetch_and_store_team_stats(sb, season)
        except Exception as e:
            log.error(f"[{season}] Team stats failed: {e}")
            continue

        if stats_only:
            continue

        if not skip_games:
            try:
                fetch_and_store_game_history(sb, season)
            except Exception as e:
                log.error(f"[{season}] Game history failed: {e}")

        if not skip_four_factors:
            try:
                fetch_and_store_four_factors(sb, season)
            except Exception as e:
                log.error(f"[{season}] Four factors failed: {e}")

        # Brief pause between seasons to be kind to ESPN API
        if i < len(seasons) - 1:
            log.info(f"  Pausing 5s before next season…")
            time.sleep(5)

    log.info(f"\n=== Backfill complete: seasons {start}–{end} ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill historical NCAAB seasons")
    parser.add_argument("--start", type=int, default=BACKFILL_START,
                        help=f"First season to backfill (default: {BACKFILL_START})")
    parser.add_argument("--end", type=int, default=BACKFILL_END,
                        help=f"Last season to backfill (default: {BACKFILL_END})")
    parser.add_argument("--season", type=int, default=None,
                        help="Backfill a single season only (overrides --start/--end)")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only fetch team stats (fast, ~5 min for all seasons)")
    parser.add_argument("--skip-games", action="store_true",
                        help="Skip game history fetch")
    parser.add_argument("--skip-four-factors", action="store_true",
                        help="Skip four factors fetch")
    args = parser.parse_args()

    start = args.season if args.season else args.start
    end   = args.season if args.season else args.end

    backfill(
        start=start,
        end=end,
        stats_only=args.stats_only,
        skip_games=args.skip_games,
        skip_four_factors=args.skip_four_factors,
    )