"""
pipeline/fetch_and_store.py
===========================
Fetches NCAAB data and upserts into Supabase.

Sources:
  - Team stats:  BartTorvik CSV
  - Game logs:   ESPN public scoreboard API
  - Four factors: ESPN game summary API (calculated from box scores)

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
SEASON_START = date(2025, 11, 1)
SEASON_END   = date(2026, 4, 7)

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
ESPN_SUMMARY    = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"

SUPABASE_PAGE = 1000   # max rows per Supabase select

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

def _get_all_ids(sb: Client, table: str) -> set:
    """Paginate through Supabase to get ALL game_ids — avoids 1000-row limit."""
    ids = set()
    offset = 0
    while True:
        resp = (sb.table(table)
                  .select("game_id")
                  .eq("season", SEASON)
                  .range(offset, offset + SUPABASE_PAGE - 1)
                  .execute())
        batch = {r["game_id"] for r in resp.data if r.get("game_id")}
        ids |= batch
        if len(batch) < SUPABASE_PAGE:
            break
        offset += SUPABASE_PAGE
    return ids


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


# ── 2. Game Logs (ESPN scoreboard) ────────────────────────────────────────────

def fetch_games_for_date(d: date) -> list[dict]:
    date_str = d.strftime("%Y%m%d")
    try:
        resp = requests.get(ESPN_SCOREBOARD,
                            params={"dates": date_str, "limit": 200, "groups": "50"},
                            timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"  ESPN fetch failed for {d}: {e}")
        return []

    rows = []
    for event in data.get("events", []):
        comp      = event["competitions"][0]
        game_id   = event["id"]
        game_date = event["date"][:10]
        status    = comp["status"]["type"]["description"]

        if status not in ("Final", "Final/OT"):
            continue

        neutral   = comp.get("neutralSite", False)
        teams     = comp["competitors"]
        if len(teams) < 2:
            continue

        team_data = {}
        for t in teams:
            team_data[t["homeAway"]] = {
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
                pf = int(t["score"]); pa = int(opp["score"])
            except (ValueError, TypeError):
                continue
            venue  = "Neutral" if neutral else ("Home" if side=="home" else "Away")
            margin = pf - pa
            rows.append({
                "season": SEASON, "game_id": game_id, "date": game_date,
                "team": t["name"], "opponent": opp["name"], "venue": venue,
                "points_for": pf, "points_against": pa,
                "margin": margin, "result": "W" if margin > 0 else "L",
            })
    return rows

def fetch_and_store_game_history(sb: Client):
    log.info("Fetching game history from ESPN API…")
    existing_ids = _get_all_ids(sb, "game_history")
    log.info(f"  {len(existing_ids)} games already in database — will skip these")

    today    = date.today()
    end      = min(today, SEASON_END)
    if len(existing_ids) > 100:
        # Scan from the most recent stored game date (catches all missed games)
        resp_last = (sb.table("game_history")
                       .select("date")
                       .eq("season", SEASON)
                       .order("date", desc=True)
                       .limit(1)
                       .execute())
        if resp_last.data and resp_last.data[0].get("date"):
            last_date = date.fromisoformat(resp_last.data[0]["date"][:10])
            start = max(SEASON_START, last_date - timedelta(days=1))  # 1 day overlap for safety
        else:
            start = max(SEASON_START, end - timedelta(days=7))
        log.info(f"  Incremental mode: scanning {start} → {end}")
    else:
        start = SEASON_START
        log.info(f"  Full mode: scanning {start} → {end}")

    all_rows = []
    skipped  = 0
    cur      = start

    while cur <= end:
        date_rows = fetch_games_for_date(cur)
        new_rows  = [r for r in date_rows if r["game_id"] not in existing_ids]
        skipped  += len(date_rows) - len(new_rows)
        all_rows.extend(new_rows)

        if len(all_rows) >= 200:
            _upsert_game_rows(sb, all_rows)
            all_rows = []

        cur += timedelta(days=1)
        time.sleep(0.15)

    if all_rows:
        _upsert_game_rows(sb, all_rows)

    new_count = len(all_rows)
    log.info(f"  ✓ Done. {skipped} skipped, {new_count} new game rows")
    log_refresh(sb, "game_history", new_count, "success")

def _upsert_game_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("game_history").upsert(
            rows[i:i+100], on_conflict="season,game_id,team"
        ).execute()
    log.info(f"  Upserted {len(rows)} game rows")


# ── 3. Four Factors (ESPN game summary box scores) ────────────────────────────

def _parse_made_att(statistics: list, name: str) -> tuple[float | None, float | None]:
    for s in statistics:
        if s.get("name") == name:
            val = s.get("displayValue", "")
            if "-" in val:
                try:
                    m, a = val.split("-")
                    return float(m), float(a)
                except ValueError:
                    pass
    return None, None

def _stat(statistics: list, name: str) -> float | None:
    for s in statistics:
        if s.get("name") == name:
            try:
                return float(s["displayValue"])
            except (ValueError, KeyError):
                pass
    return None

def _has_real_data(statistics: list) -> bool:
    """Return True only if the stats list has meaningful box score data."""
    fgm, fga = _parse_made_att(statistics, "fieldGoalsMade-fieldGoalsAttempted")
    return fga is not None and fga > 0

def calc_four_factors(stats: list, opp_stats: list) -> dict:
    # If either team has no real box score data, return all None
    if not _has_real_data(stats) or not _has_real_data(opp_stats):
        return {k: None for k in ["efg_pct","tov_pct","orb_pct","ftr",
                                   "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]}

    fgm,  fga  = _parse_made_att(stats, "fieldGoalsMade-fieldGoalsAttempted")
    tpm,  _    = _parse_made_att(stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    _,    fta  = _parse_made_att(stats, "freeThrowsMade-freeThrowsAttempted")
    tov        = _stat(stats, "totalTurnovers") or 0.0
    orb        = _stat(stats, "offensiveRebounds") or 0.0
    drb        = _stat(stats, "defensiveRebounds") or 0.0
    fgm  = fgm  or 0.0; fga  = fga  or 0.0
    tpm  = tpm  or 0.0; fta  = fta  or 0.0

    opp_fgm, opp_fga = _parse_made_att(opp_stats, "fieldGoalsMade-fieldGoalsAttempted")
    opp_tpm, _       = _parse_made_att(opp_stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    _, opp_fta       = _parse_made_att(opp_stats, "freeThrowsMade-freeThrowsAttempted")
    opp_tov          = _stat(opp_stats, "totalTurnovers") or 0.0
    opp_orb          = _stat(opp_stats, "offensiveRebounds") or 0.0
    opp_drb          = _stat(opp_stats, "defensiveRebounds") or 0.0
    opp_fgm = opp_fgm or 0.0; opp_fga = opp_fga or 0.0
    opp_tpm = opp_tpm or 0.0; opp_fta = opp_fta or 0.0

    def safe(num, den):
        return round(num / den, 4) if den and den > 0 else None

    return {
        "efg_pct":     safe(fgm + 0.5 * tpm,  fga),
        "tov_pct":     safe(tov, fga + 0.44 * fta + tov),
        "orb_pct":     safe(orb, orb + opp_drb),
        "ftr":         safe(fta, fga),
        "opp_efg_pct": safe(opp_fgm + 0.5 * opp_tpm, opp_fga),
        "opp_tov_pct": safe(opp_tov, opp_fga + 0.44 * opp_fta + opp_tov),
        "opp_orb_pct": safe(opp_orb, opp_orb + drb),
        "opp_ftr":     safe(opp_fta, opp_fga),
    }

def fetch_and_store_four_factors(sb: Client):
    log.info("Fetching four factors from ESPN game summaries…")

    # Get all game IDs from game_history (paginated)
    resp = (sb.table("game_history")
              .select("game_id,date,team,opponent")
              .eq("season", SEASON)
              .execute())
    if not resp.data:
        log.warning("  No game history — skipping four factors")
        return

    # Paginate to get ALL existing adv IDs
    existing_adv = _get_all_ids(sb, "adv_game_history")
    all_game_ids = list({r["game_id"] for r in resp.data})
    new_game_ids = [gid for gid in all_game_ids if gid not in existing_adv]
    log.info(f"  {len(existing_adv)} games already have adv stats — fetching {len(new_game_ids)} new")

    if not new_game_ids:
        log.info("  ✓ All games already have four factors — nothing to do")
        _aggregate_four_factors_to_team_stats(sb)
        return

    # Build game_id -> meta lookup
    game_meta = {}
    for r in resp.data:
        gid = r["game_id"]
        if gid not in game_meta:
            game_meta[gid] = r

    adv_rows = []
    errors   = 0

    for i, game_id in enumerate(new_game_ids):
        try:
            resp_s = requests.get(ESPN_SUMMARY, params={"event": game_id}, timeout=15)
            resp_s.raise_for_status()
            data = resp_s.json()

            box_teams = data.get("boxscore", {}).get("teams", [])
            if len(box_teams) < 2:
                continue

            team_stats_map = {bt["team"]["displayName"]: bt.get("statistics", [])
                              for bt in box_teams}
            team_names = list(team_stats_map.keys())
            if len(team_names) < 2:
                continue

            t1, t2 = team_names[0], team_names[1]
            game_date = game_meta.get(game_id, {}).get("date", "")

            adv_rows.append({"season": SEASON, "game_id": game_id, "date": game_date,
                             "team": t1, "opponent": t2,
                             **calc_four_factors(team_stats_map[t1], team_stats_map[t2])})
            adv_rows.append({"season": SEASON, "game_id": game_id, "date": game_date,
                             "team": t2, "opponent": t1,
                             **calc_four_factors(team_stats_map[t2], team_stats_map[t1])})

        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning(f"  Error on game {game_id}: {e}")

        if len(adv_rows) >= 200:
            _upsert_adv_rows(sb, adv_rows)
            adv_rows = []

        if i % 50 == 0 and i > 0:
            log.info(f"  Progress: {i}/{len(new_game_ids)} games processed")

        time.sleep(0.2)

    if adv_rows:
        _upsert_adv_rows(sb, adv_rows)

    log.info(f"  ✓ Four factors stored. {len(new_game_ids) - errors} games, {errors} errors")
    log_refresh(sb, "adv_game_history", len(new_game_ids) - errors, "success")
    _aggregate_four_factors_to_team_stats(sb)

def _upsert_adv_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("adv_game_history").upsert(
            rows[i:i+100], on_conflict="season,game_id,team"
        ).execute()
    log.info(f"  Upserted {len(rows)} adv game rows")

def _aggregate_four_factors_to_team_stats(sb: Client):
    log.info("  Aggregating four factors to team season averages…")

    # Paginate adv_game_history
    all_rows = []
    offset   = 0
    while True:
        resp = (sb.table("adv_game_history")
                  .select("*")
                  .eq("season", SEASON)
                  .range(offset, offset + SUPABASE_PAGE - 1)
                  .execute())
        all_rows.extend(resp.data)
        if len(resp.data) < SUPABASE_PAGE:
            break
        offset += SUPABASE_PAGE

    if not all_rows:
        log.warning("  No adv_game_history data to aggregate")
        return

    df = pd.DataFrame(all_rows)
    ff_cols = ["efg_pct","tov_pct","orb_pct","ftr",
               "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]
    for c in ff_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    avgs = df.groupby("team")[[c for c in ff_cols if c in df.columns]].mean().reset_index()

    ts_resp = sb.table("team_stats").select("team").eq("season", SEASON).execute()
    bart_names = [r["team"] for r in ts_resp.data]

    # Build ESPN->BartTorvik lookup using name_map if available
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
        import name_map as nm
        espn_names = df["team"].unique().tolist()
        nm.build(bart_names, espn_names)
        def find_bart(espn_name):
            # to_espn gives us the canonical ESPN name, we need the reverse
            # Try direct clean match
            clean_espn = str(espn_name).lower().strip()
            for b in bart_names:
                if nm.to_espn(b).lower() == clean_espn:
                    return b
            return None
    except Exception:
        find_bart = None

    def clean(n):
        return str(n).lower().split()[0] if n else ""

    bart_clean = {}
    for b in bart_names:
        fw = clean(b)
        if fw not in bart_clean:
            bart_clean[fw] = b  # first-word fallback (may collide for Saint/* teams)

    updated = 0
    for _, row in avgs.iterrows():
        espn_name = row["team"]
        # Try name_map reverse lookup first
        bart_name = None
        if find_bart:
            bart_name = find_bart(espn_name)
        # Fallback: strip mascot suffix and match
        if not bart_name:
            stripped = str(espn_name).lower()
            for b in bart_names:
                if stripped.startswith(str(b).lower()) or str(b).lower() in stripped:
                    bart_name = b
                    break
        # Last resort: first-word match
        if not bart_name:
            bart_name = bart_clean.get(clean(espn_name))
        if not bart_name:
            continue
        update = {c: round(float(row[c]), 4) for c in ff_cols
                  if c in row and not pd.isna(row.get(c))}
        if update:
            sb.table("team_stats").update(update)\
              .eq("season", SEASON).eq("team", bart_name).execute()
            updated += 1

    log.info(f"  ✓ Updated four factors for {updated} teams in team_stats")
    log_refresh(sb, "four_factors", updated, "success")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"=== NCAAB pipeline starting — season {SEASON} ===")
    sb = get_supabase()
    fetch_and_store_team_stats(sb)
    fetch_and_store_game_history(sb)
    fetch_and_store_four_factors(sb)
    log.info("=== Pipeline complete ===")