"""
pipeline/fetch_and_store.py
===========================
Fetches NCAAB data from BartTorvik + ESPN (via cbbpy)
and upserts everything into Supabase.

Run manually:   python pipeline/fetch_and_store.py
Run via cron:   GitHub Actions calls this nightly (see .github/workflows/nightly.yml)

Required env vars (set in GitHub Actions secrets or a local .env file):
  SUPABASE_URL   — e.g. https://xxxx.supabase.co
  SUPABASE_KEY   — service_role key (not the anon key)
"""

import os, sys, time, logging
from io import StringIO
from datetime import datetime

import requests
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SEASON = 2026   # ← update each year

# ── Supabase client ───────────────────────────────────────────────────────────

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "Missing SUPABASE_URL or SUPABASE_KEY environment variables.\n"
            "Create a .env file or export them in your shell."
        )
    return create_client(url, key)


def log_refresh(sb: Client, data_type: str, rows: int, status: str, message: str = ""):
    sb.table("refresh_log").insert({
        "data_type": data_type,
        "season": SEASON,
        "rows_upserted": rows,
        "status": status,
        "message": message,
    }).execute()


# ── 1. Team Stats (BartTorvik) ────────────────────────────────────────────────

def fetch_and_store_team_stats(sb: Client):
    log.info("Fetching team stats from BartTorvik…")
    url = f"https://barttorvik.com/{SEASON}_team_results.csv"
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error(f"BartTorvik fetch failed: {e}")
        log_refresh(sb, "team_stats", 0, "error", str(e))
        return

    df = pd.read_csv(StringIO(resp.text), header=0)
    df.columns = [c.strip().lower() for c in df.columns]

    col_rename = {
        "team": "team", "conf": "conference", "record": "record",
        "adjoe": "adj_oe", "adjde": "adj_de", "adjt": "adj_tempo",
        "luck": "luck", "sos": "sos_oe", "ncsos": "ncsos",
    }
    df = df.rename(columns=col_rename)

    numeric_cols = ["adj_oe", "adj_de", "adj_tempo", "luck"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "adj_oe" in df.columns and "adj_de" in df.columns:
        df["net_eff"] = df["adj_oe"] - df["adj_de"]

    df["season"] = SEASON
    df = df.dropna(subset=["team"])

    keep = ["season","team","conference","record","adj_oe","adj_de","adj_tempo",
            "net_eff","luck","sos_oe","ncsos"]
    rows = df[[c for c in keep if c in df.columns]].to_dict(orient="records")

    # Upsert in batches of 100
    upserted = 0
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        sb.table("team_stats").upsert(batch, on_conflict="season,team").execute()
        upserted += len(batch)

    log.info(f"  ✓ Upserted {upserted} team stat rows")
    log_refresh(sb, "team_stats", upserted, "success")


# ── 2. Game History (CBBpy / ESPN) ────────────────────────────────────────────

def fetch_and_store_game_history(sb: Client):
    log.info("Fetching game history via cbbpy…")
    try:
        import cbbpy.mens_scraper as cbb
    except ImportError:
        log.error("cbbpy not installed. Run: pip install cbbpy")
        log_refresh(sb, "game_history", 0, "error", "cbbpy not installed")
        return

    try:
        info_df, box_df, _ = cbb.get_games_season(SEASON, info=True, box=True, pbp=False)
    except Exception as e:
        log.error(f"cbbpy season fetch failed: {e}")
        log_refresh(sb, "game_history", 0, "error", str(e))
        return

    if info_df is None or info_df.empty:
        log.warning("No game data returned from cbbpy")
        log_refresh(sb, "game_history", 0, "error", "No data returned")
        return

    log.info(f"  Got {len(info_df)} game records. Processing…")

    basic_rows = []
    adv_rows   = []

    for _, row in info_df.iterrows():
        gid      = row.get("game_id", "")
        date     = str(row.get("game_day", ""))
        neutral  = bool(row.get("is_neutral", False))
        home_pts = row.get("home_score")
        away_pts = row.get("away_score")

        for side in ["home", "away"]:
            opp_side = "away" if side == "home" else "home"
            team  = row.get(f"{side}_team", "")
            opp   = row.get(f"{opp_side}_team", "")
            pf    = home_pts if side == "home" else away_pts
            pa    = away_pts if side == "home" else home_pts
            venue = "Neutral" if neutral else ("Home" if side == "home" else "Away")

            if not team:
                continue

            try:
                pf_int = int(pf) if pf is not None else None
                pa_int = int(pa) if pa is not None else None
                margin = (pf_int - pa_int) if pf_int is not None and pa_int is not None else None
                result = ("W" if margin > 0 else "L") if margin is not None else None
            except Exception:
                pf_int = pa_int = margin = result = None

            basic_rows.append({
                "season": SEASON, "game_id": str(gid), "date": date,
                "team": team, "opponent": opp, "venue": venue,
                "points_for": pf_int, "points_against": pa_int,
                "margin": margin, "result": result,
                "tempo": row.get("tempo"), "possessions": row.get("num_ot"),
            })

    # Upsert basic game history
    upserted_basic = 0
    for i in range(0, len(basic_rows), 100):
        batch = basic_rows[i:i+100]
        sb.table("game_history").upsert(batch, on_conflict="season,game_id,team").execute()
        upserted_basic += len(batch)
    log.info(f"  ✓ Upserted {upserted_basic} game history rows")
    log_refresh(sb, "game_history", upserted_basic, "success")

    # Advanced four factors from box scores
    if box_df is not None and not box_df.empty:
        totals = box_df[box_df.get("player", pd.Series(dtype=str)) == "Team Totals"] \
                 if "player" in box_df.columns else pd.DataFrame()

        for _, tr in totals.iterrows():
            adv_rows.append({
                "season":      SEASON,
                "game_id":     str(tr.get("game_id", "")),
                "date":        str(tr.get("date", "")),
                "team":        tr.get("team", ""),
                "opponent":    tr.get("opponent", ""),
                "efg_pct":     tr.get("efg_pct"),
                "tov_pct":     tr.get("tov_pct"),
                "orb_pct":     tr.get("orb_pct"),
                "ftr":         tr.get("ftr"),
                "opp_efg_pct": tr.get("opp_efg_pct"),
                "opp_tov_pct": tr.get("opp_tov_pct"),
                "opp_orb_pct": tr.get("opp_orb_pct"),
                "opp_ftr":     tr.get("opp_ftr"),
            })

        upserted_adv = 0
        for i in range(0, len(adv_rows), 100):
            batch = adv_rows[i:i+100]
            sb.table("adv_game_history").upsert(batch, on_conflict="season,game_id,team").execute()
            upserted_adv += len(batch)
        log.info(f"  ✓ Upserted {upserted_adv} advanced game history rows")
        log_refresh(sb, "adv_game_history", upserted_adv, "success")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"=== NCAAB pipeline starting — season {SEASON} ===")
    sb = get_supabase()

    fetch_and_store_team_stats(sb)
    fetch_and_store_game_history(sb)

    log.info("=== Pipeline complete ===")
