"""
pipeline/fetch_and_store.py
===========================
Fetches NCAAB data and upserts into Supabase.

Sources:
  - Team stats:  BartTorvik CSV
  - Game logs:   ESPN public API (no key needed)

Run manually:   python pipeline/fetch_and_store.py
Scheduled:      GitHub Actions nightly (see .github/workflows/nightly.yml)

Required env vars:
  SUPABASE_URL
  SUPABASE_KEY
"""

import os, time, logging
from io import StringIO
from datetime import date, timedelta

import requests
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SEASON       = 2026
SEASON_START = date(2025, 11, 1)   # first day of games
SEASON_END   = date(2026, 4, 7)    # national championship

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(url, key)

def log_refresh(sb, data_type, rows, status, message=""):
    sb.table("refresh_log").insert({
        "data_type": data_type, "season": SEASON,
        "rows_upserted": rows, "status": status, "message": message,
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
    df = df.rename(columns={
        "team": "team", "conf": "conference", "record": "record",
        "adjoe": "adj_oe", "adjde": "adj_de", "adjt": "adj_tempo",
        "luck": "luck", "sos": "sos_oe", "ncsos": "ncsos",
    })
    for c in ["adj_oe", "adj_de", "adj_tempo"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "adj_oe" in df.columns and "adj_de" in df.columns:
        df["net_eff"] = df["adj_oe"] - df["adj_de"]
    df = df.dropna(subset=["team"])
    df["season"] = SEASON

    keep = ["season","team","conference","record","adj_oe","adj_de",
            "adj_tempo","net_eff","luck","sos_oe","ncsos"]
    rows = df[[c for c in keep if c in df.columns]].to_dict(orient="records")

    upserted = 0
    for i in range(0, len(rows), 100):
        sb.table("team_stats").upsert(rows[i:i+100], on_conflict="season,team").execute()
        upserted += len(rows[i:i+100])

    log.info(f"  ✓ {upserted} team stat rows upserted")
    log_refresh(sb, "team_stats", upserted, "success")


# ── 2. Game Logs (ESPN API) ───────────────────────────────────────────────────

def get_existing_game_ids(sb: Client) -> set:
    """Fetch game IDs already in Supabase so we can skip them."""
    resp = (sb.table("game_history")
              .select("game_id")
              .eq("season", SEASON)
              .execute())
    return {r["game_id"] for r in resp.data if r.get("game_id")}

def fetch_games_for_date(d: date) -> list[dict]:
    """Fetch all games for a single date from ESPN API."""
    date_str = d.strftime("%Y%m%d")
    try:
        resp = requests.get(ESPN_SCOREBOARD,
                            params={"dates": date_str, "limit": 100},
                            timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"  ESPN fetch failed for {d}: {e}")
        return []

    rows = []
    for event in data.get("events", []):
        comp     = event["competitions"][0]
        game_id  = event["id"]
        game_date = event["date"][:10]   # "2026-03-01"
        status   = comp["status"]["type"]["description"]

        if status not in ("Final", "Final/OT"):
            continue  # skip in-progress or scheduled games

        neutral  = comp.get("neutralSite", False)
        teams    = comp["competitors"]
        if len(teams) < 2:
            continue

        # Build team lookup
        team_data = {}
        for t in teams:
            side = t["homeAway"]   # "home" or "away"
            team_data[side] = {
                "name":  t["team"]["displayName"],
                "score": t.get("score", 0),
            }

        home = team_data.get("home", {})
        away = team_data.get("away", {})
        if not home or not away:
            continue

        for side, opp_side in [("home","away"),("away","home")]:
            t   = team_data[side]
            opp = team_data[opp_side]
            try:
                pf = int(t["score"])
                pa = int(opp["score"])
            except (ValueError, TypeError):
                continue

            venue  = "Neutral" if neutral else ("Home" if side == "home" else "Away")
            margin = pf - pa
            result = "W" if margin > 0 else "L"

            rows.append({
                "season":         SEASON,
                "game_id":        game_id,
                "date":           game_date,
                "team":           t["name"],
                "opponent":       opp["name"],
                "venue":          venue,
                "points_for":     pf,
                "points_against": pa,
                "margin":         margin,
                "result":         result,
            })
    return rows

def fetch_and_store_game_history(sb: Client):
    log.info("Fetching game history from ESPN API…")

    existing_ids = get_existing_game_ids(sb)
    log.info(f"  {len(existing_ids)} games already in database — will skip these")

    today      = date.today()
    end        = min(today, SEASON_END)
    all_rows   = []
    skipped    = 0
    cur        = SEASON_START

    while cur <= end:
        date_rows = fetch_games_for_date(cur)
        new_rows  = [r for r in date_rows if r["game_id"] not in existing_ids]
        skipped  += len(date_rows) - len(new_rows)
        all_rows.extend(new_rows)

        if len(all_rows) >= 200:
            _upsert_game_rows(sb, all_rows)
            all_rows = []

        cur += timedelta(days=1)
        time.sleep(0.15)   # polite rate limiting

    if all_rows:
        _upsert_game_rows(sb, all_rows)

    log.info(f"  ✓ Done. {skipped} games skipped (already stored)")
    log_refresh(sb, "game_history", skipped, "success", f"{skipped} skipped")

def _upsert_game_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("game_history").upsert(
            rows[i:i+100], on_conflict="season,game_id,team"
        ).execute()
    log.info(f"  Upserted {len(rows)} game rows")


# ── 3. Four Factors (aggregated from game history via BartTorvik) ─────────────

def compute_and_store_four_factors(sb: Client):
    """
    ESPN API doesn't return four factors directly.
    We pull them from BartTorvik's trank page which has per-team season averages.
    Falls back gracefully if the page blocks us.
    """
    log.info("Fetching four factors from BartTorvik trank…")
    url = f"https://barttorvik.com/trank.php?year={SEASON}&csv=1"
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Try parsing — BartTorvik sometimes returns HTML bot-check
        if "<html" in resp.text[:200].lower():
            raise ValueError("Got HTML instead of CSV (bot check)")
        df = pd.read_csv(StringIO(resp.text), header=0, on_bad_lines="skip")
        df.columns = [c.strip().lower() for c in df.columns]

        ff_rename = {}
        for c in df.columns:
            cl = c.lower().strip()
            if   "efg" in cl and "opp" not in cl:   ff_rename[c] = "efg_pct"
            elif "tov" in cl and "opp" not in cl:   ff_rename[c] = "tov_pct"
            elif "orb" in cl and "opp" not in cl:   ff_rename[c] = "orb_pct"
            elif "ftr" in cl and "opp" not in cl:   ff_rename[c] = "ftr"
            elif "efg" in cl and "opp" in cl:       ff_rename[c] = "opp_efg_pct"
            elif "tov" in cl and "opp" in cl:       ff_rename[c] = "opp_tov_pct"
            elif "orb" in cl and "opp" in cl:       ff_rename[c] = "opp_orb_pct"
            elif "ftr" in cl and "opp" in cl:       ff_rename[c] = "opp_ftr"
            elif cl in ["team","squad","school"]:   ff_rename[c] = "team"
        df = df.rename(columns=ff_rename)

        ff_cols = ["efg_pct","tov_pct","orb_pct","ftr",
                   "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]
        available = [c for c in ff_cols if c in df.columns]

        if "team" not in df.columns or not available:
            raise ValueError(f"Missing expected columns. Got: {df.columns.tolist()}")

        updated = 0
        for _, row in df.iterrows():
            update = {c: round(float(row[c]),4) for c in available
                      if not pd.isna(row.get(c))}
            if update and row.get("team"):
                sb.table("team_stats").update(update)\
                  .eq("season", SEASON).eq("team", row["team"]).execute()
                updated += 1
        log.info(f"  ✓ Four factors updated for {updated} teams")
        log_refresh(sb, "four_factors", updated, "success")

    except Exception as e:
        log.warning(f"  Four factors fetch failed: {e} — skipping")
        log_refresh(sb, "four_factors", 0, "error", str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"=== NCAAB pipeline starting — season {SEASON} ===")
    sb = get_supabase()
    fetch_and_store_team_stats(sb)
    fetch_and_store_game_history(sb)
    compute_and_store_four_factors(sb)
    log.info("=== Pipeline complete ===")