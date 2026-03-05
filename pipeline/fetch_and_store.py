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


# ── 2. Game Logs (ESPN scoreboard) ────────────────────────────────────────────

def get_existing_game_ids(sb: Client) -> set:
    resp = (sb.table("game_history")
              .select("game_id")
              .eq("season", SEASON)
              .execute())
    return {r["game_id"] for r in resp.data if r.get("game_id")}

def fetch_games_for_date(d: date) -> list[dict]:
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
    existing_ids = get_existing_game_ids(sb)
    log.info(f"  {len(existing_ids)} games already in database — will skip these")

    today    = date.today()
    end      = min(today, SEASON_END)
    all_rows = []
    skipped  = 0
    cur      = SEASON_START

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

    log.info(f"  ✓ Done. {skipped} games skipped (already stored)")
    log_refresh(sb, "game_history", skipped, "success", f"{skipped} skipped")

def _upsert_game_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("game_history").upsert(
            rows[i:i+100], on_conflict="season,game_id,team"
        ).execute()
    log.info(f"  Upserted {len(rows)} game rows")


# ── 3. Four Factors (ESPN game summary box scores) ────────────────────────────

def _stat(statistics: list, name: str) -> float | None:
    """Extract a stat value by name from ESPN's statistics array."""
    for s in statistics:
        if s.get("name") == name:
            try:
                return float(s["displayValue"])
            except (ValueError, KeyError):
                # Some stats are formatted as "made-attempted" — parse those
                val = s.get("displayValue", "")
                if "-" in val:
                    parts = val.split("-")
                    try:
                        return float(parts[0]), float(parts[1])
                    except ValueError:
                        pass
    return None

def _parse_made_att(statistics: list, name: str) -> tuple[float, float]:
    """Parse a 'made-attempted' stat, returns (made, attempted)."""
    for s in statistics:
        if s.get("name") == name:
            val = s.get("displayValue", "")
            if "-" in val:
                try:
                    m, a = val.split("-")
                    return float(m), float(a)
                except ValueError:
                    pass
    return 0.0, 0.0

def calc_four_factors(stats: list, opp_stats: list) -> dict:
    """
    Calculate four factors from ESPN box score statistics arrays.

    eFG%  = (FGM + 0.5 * 3PM) / FGA
    TOV%  = TOV / (FGA + 0.44 * FTA + TOV)
    ORB%  = ORB / (ORB + opp_DRB)
    FTR   = FTA / FGA
    """
    fgm,  fga  = _parse_made_att(stats, "fieldGoalsMade-fieldGoalsAttempted")
    tpm,  tpa  = _parse_made_att(stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    ftm,  fta  = _parse_made_att(stats, "freeThrowsMade-freeThrowsAttempted")
    tov        = _stat(stats, "totalTurnovers") or 0.0
    orb        = _stat(stats, "offensiveRebounds") or 0.0
    drb        = _stat(stats, "defensiveRebounds") or 0.0

    _, opp_fga = _parse_made_att(opp_stats, "fieldGoalsMade-fieldGoalsAttempted")
    _, opp_tpa = _parse_made_att(opp_stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    _, opp_fta = _parse_made_att(opp_stats, "freeThrowsMade-freeThrowsAttempted")
    opp_tov    = _stat(opp_stats, "totalTurnovers") or 0.0
    opp_orb    = _stat(opp_stats, "offensiveRebounds") or 0.0
    opp_drb    = _stat(opp_stats, "defensiveRebounds") or 0.0
    opp_fgm, _ = _parse_made_att(opp_stats, "fieldGoalsMade-fieldGoalsAttempted")
    opp_tpm, _ = _parse_made_att(opp_stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")

    def safe(num, den):
        return round(num / den, 4) if den > 0 else None

    efg     = safe(fgm + 0.5 * tpm,  fga)
    tov_pct = safe(tov, fga + 0.44 * fta + tov)
    orb_pct = safe(orb, orb + opp_drb)
    ftr     = safe(fta, fga)

    opp_efg     = safe(opp_fgm + 0.5 * opp_tpm, opp_fga)
    opp_tov_pct = safe(opp_tov, opp_fga + 0.44 * opp_fta + opp_tov)
    opp_orb_pct = safe(opp_orb, opp_orb + drb)
    opp_ftr     = safe(opp_fta, opp_fga)

    return {
        "efg_pct":     efg,
        "tov_pct":     tov_pct,
        "orb_pct":     orb_pct,
        "ftr":         ftr,
        "opp_efg_pct": opp_efg,
        "opp_tov_pct": opp_tov_pct,
        "opp_orb_pct": opp_orb_pct,
        "opp_ftr":     opp_ftr,
    }

def get_existing_adv_game_ids(sb: Client) -> set:
    resp = (sb.table("adv_game_history")
              .select("game_id")
              .eq("season", SEASON)
              .execute())
    return {r["game_id"] for r in resp.data if r.get("game_id")}

def fetch_and_store_four_factors(sb: Client):
    """
    For every game in game_history that doesn't have adv stats yet,
    hit the ESPN summary endpoint, calculate four factors, store in adv_game_history.
    Then aggregate to season averages and update team_stats.
    """
    log.info("Fetching four factors from ESPN game summaries…")

    # Get all game IDs we have scores for
    resp = (sb.table("game_history")
              .select("game_id,date,team,opponent")
              .eq("season", SEASON)
              .execute())
    if not resp.data:
        log.warning("  No game history found — skipping four factors")
        return

    # Only process games not already in adv_game_history
    existing_adv = get_existing_adv_game_ids(sb)
    all_game_ids = list({r["game_id"] for r in resp.data})
    new_game_ids = [gid for gid in all_game_ids if gid not in existing_adv]
    log.info(f"  {len(existing_adv)} games already have adv stats — fetching {len(new_game_ids)} new")

    # Build game_id -> {team, opponent, date} lookup
    game_meta = {}
    for r in resp.data:
        gid = r["game_id"]
        if gid not in game_meta:
            game_meta[gid] = []
        game_meta[gid].append(r)

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

            # Map displayName -> statistics
            team_stats_map = {}
            for bt in box_teams:
                name = bt["team"]["displayName"]
                team_stats_map[name] = bt.get("statistics", [])

            team_names = list(team_stats_map.keys())
            if len(team_names) < 2:
                continue

            t1, t2 = team_names[0], team_names[1]
            ff1 = calc_four_factors(team_stats_map[t1], team_stats_map[t2])
            ff2 = calc_four_factors(team_stats_map[t2], team_stats_map[t1])

            # Get date from meta
            meta = game_meta.get(game_id, [{}])
            game_date = meta[0].get("date", "")

            adv_rows.append({"season": SEASON, "game_id": game_id, "date": game_date,
                             "team": t1, "opponent": t2, **ff1})
            adv_rows.append({"season": SEASON, "game_id": game_id, "date": game_date,
                             "team": t2, "opponent": t1, **ff2})

        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning(f"  Error on game {game_id}: {e}")

        # Upsert in batches of 200
        if len(adv_rows) >= 200:
            _upsert_adv_rows(sb, adv_rows)
            adv_rows = []

        if i % 50 == 0 and i > 0:
            log.info(f"  Progress: {i}/{len(new_game_ids)} games processed")

        time.sleep(0.2)  # polite rate limiting

    if adv_rows:
        _upsert_adv_rows(sb, adv_rows)

    log.info(f"  ✓ Four factors stored. Errors: {errors}")
    log_refresh(sb, "adv_game_history", len(new_game_ids) - errors, "success")

    # Now aggregate to season averages and update team_stats
    _aggregate_four_factors_to_team_stats(sb)

def _upsert_adv_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("adv_game_history").upsert(
            rows[i:i+100], on_conflict="season,game_id,team"
        ).execute()
    log.info(f"  Upserted {len(rows)} adv game rows")

def _aggregate_four_factors_to_team_stats(sb: Client):
    """Average per-game four factors into season totals and push to team_stats."""
    log.info("  Aggregating four factors to team season averages…")

    resp = sb.table("adv_game_history").select("*").eq("season", SEASON).execute()
    if not resp.data:
        log.warning("  No adv_game_history data to aggregate")
        return

    df = pd.DataFrame(resp.data)
    ff_cols = ["efg_pct","tov_pct","orb_pct","ftr",
               "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]
    for c in ff_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    avgs = df.groupby("team")[[c for c in ff_cols if c in df.columns]].mean().reset_index()

    # Map ESPN names to BartTorvik names for team_stats update
    # Load BartTorvik names from team_stats
    ts_resp = sb.table("team_stats").select("team").eq("season", SEASON).execute()
    bart_names = [r["team"] for r in ts_resp.data]

    # Simple fuzzy match: strip mascot words and match on first token
    def clean(n):
        return str(n).lower().split()[0] if n else ""

    bart_clean = {clean(b): b for b in bart_names}

    updated = 0
    for _, row in avgs.iterrows():
        espn_name = row["team"]
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