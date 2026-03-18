"""
pipeline/fetch_and_store.py
===========================
Fetches NCAAB data and upserts into Supabase.

Sources:
  - Team stats:  BartTorvik CSV
  - Game logs:   ESPN public scoreboard API
  - Four factors: ESPN game summary API (calculated from box scores)

Run manually:
  python pipeline/fetch_and_store.py                  # current season (2026)
  python pipeline/fetch_and_store.py --season 2024    # specific season

Flags:
  --stats-only          Only fetch team stats (no ESPN calls)
  --skip-games          Skip game history
  --skip-four-factors   Skip four factors

Scheduled: GitHub Actions nightly
"""

import os, sys, time, logging, argparse
from io import StringIO
from datetime import date, timedelta

import requests
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DEFAULT_SEASON = 2026
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
ESPN_SUMMARY    = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
SUPABASE_PAGE   = 1000

def season_dates(season: int) -> tuple:
    """Return (start, end) dates for a given season year."""
    return date(season - 1, 11, 1), date(season, 4, 15)

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(url, key)

def log_refresh(sb, data_type, rows, status, season, message=""):
    sb.table("refresh_log").insert({
        "data_type": data_type, "season": season,
        "rows_upserted": rows, "status": status, "message": message,
    }).execute()

def _get_all_ids(sb: Client, table: str, season: int) -> set:
    ids, offset = set(), 0
    while True:
        resp = (sb.table(table).select("game_id").eq("season", season)
                  .range(offset, offset + SUPABASE_PAGE - 1).execute())
        batch = {r["game_id"] for r in resp.data if r.get("game_id")}
        ids |= batch
        if len(batch) < SUPABASE_PAGE:
            break
        offset += SUPABASE_PAGE
    return ids


# ── 1. Team Stats ─────────────────────────────────────────────────────────────

def fetch_and_store_team_stats(sb: Client, season: int):
    log.info(f"[{season}] Fetching team stats from BartTorvik…")
    url = f"https://barttorvik.com/{season}_team_results.csv"
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error(f"[{season}] BartTorvik fetch failed: {e}")
        log_refresh(sb, "team_stats", 0, "error", season, str(e))
        return

    df = pd.read_csv(StringIO(resp.text), header=0)
    df.columns = [c.strip().lower() for c in df.columns]

    # Older Torvik CSVs (pre-2022) have an extra leading 'rank' column that
    # shifts everything: 'rank'=team name, 'team'=conf, 'conf'=record, etc.
    # Detect by checking if 'team' column values look like conference names.
    if "rank" in df.columns and "team" in df.columns:
        sample = df["team"].dropna().head(10).tolist()
        conf_like = sum(1 for v in sample if isinstance(v, str) and len(str(v)) <= 5)
        if conf_like >= 7:
            log.info(f"[{season}]   Detected shifted columns — correcting alignment")
            # Drop the 'rank' header and shift all column names one position left
            # so rank->team, team->conf, conf->record, record->adjoe, etc.
            old_cols = df.columns.tolist()          # [rank, team, conf, record, adjoe, ...]
            new_cols = old_cols[1:] + ["_overflow"] # [team, conf, record, adjoe, ..., _overflow]
            df.columns = new_cols
            df = df.drop(columns=["_overflow"], errors="ignore")

    # Handle older CSVs where adjt is part of last column name e.g. "fun rk, adjt"
    adjt_candidates = [c for c in df.columns if "adjt" in c and c != "adjt"]
    for col in adjt_candidates:
        df = df.rename(columns={col: "adjt"})
        break

    df = df.rename(columns={
        "conf": "conference", "record": "record",
        "adjoe": "adj_oe", "adjde": "adj_de", "adjt": "adj_tempo",
        "luck": "luck", "sos": "sos_oe", "ncsos": "ncsos",
    })
    for c in ["adj_oe", "adj_de", "adj_tempo"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "adj_oe" in df.columns and "adj_de" in df.columns:
        df["net_eff"] = df["adj_oe"] - df["adj_de"]
    df = df.dropna(subset=["team"])
    df["season"] = season
    log.info(f"[{season}]   CSV rows after dropna: {len(df)}, columns present: {[c for c in ['team','adj_oe','adj_de','adj_tempo','sos_oe','ncsos','luck'] if c in df.columns]}")

    keep = ["season","team","conference","record","adj_oe","adj_de",
            "adj_tempo","net_eff","luck","sos_oe","ncsos"]
    df = df[[c for c in keep if c in df.columns]]

    # Deduplicate on (season, team) — older Torvik CSVs sometimes have duplicate rows
    before = len(df)
    df = df.drop_duplicates(subset=["season","team"], keep="first")
    if len(df) < before:
        log.info(f"[{season}]   Dropped {before - len(df)} duplicate team rows")

    rows = df.to_dict(orient="records")

    upserted = 0
    for i in range(0, len(rows), 100):
        sb.table("team_stats").upsert(rows[i:i+100], on_conflict="season,team").execute()
        upserted += len(rows[i:i+100])

    log.info(f"[{season}]   ✓ {upserted} team stat rows upserted")
    log_refresh(sb, "team_stats", upserted, "success", season)


# ── 2. Game History ───────────────────────────────────────────────────────────

def fetch_games_for_date(d: date, season: int) -> list:
    try:
        resp = requests.get(ESPN_SCOREBOARD,
                            params={"dates": d.strftime("%Y%m%d"), "limit": 200, "groups": "50"},
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
        if comp["status"]["type"]["description"] not in ("Final", "Final/OT"):
            continue
        neutral = comp.get("neutralSite", False)
        teams   = comp["competitors"]
        if len(teams) < 2:
            continue
        team_data = {t["homeAway"]: {"name": t["team"]["displayName"], "score": t.get("score", 0)}
                     for t in teams}
        if not team_data.get("home") or not team_data.get("away"):
            continue
        for side, opp_side in [("home","away"),("away","home")]:
            t, opp = team_data[side], team_data[opp_side]
            try:
                pf, pa = int(t["score"]), int(opp["score"])
            except (ValueError, TypeError):
                continue
            margin = pf - pa
            rows.append({
                "season": season, "game_id": game_id, "date": game_date,
                "team": t["name"], "opponent": opp["name"],
                "venue": "Neutral" if neutral else ("Home" if side=="home" else "Away"),
                "points_for": pf, "points_against": pa,
                "margin": margin, "result": "W" if margin > 0 else "L",
            })
    return rows

def fetch_and_store_game_history(sb: Client, season: int):
    season_start, season_end = season_dates(season)
    log.info(f"[{season}] Fetching game history from ESPN API…")
    existing_ids = _get_all_ids(sb, "game_history", season)
    log.info(f"[{season}]   {len(existing_ids)} games already in DB — skipping")

    today = date.today()
    end   = min(today, season_end)

    if len(existing_ids) > 100:
        resp_last = (sb.table("game_history").select("date").eq("season", season)
                       .order("date", desc=True).limit(1).execute())
        if resp_last.data and resp_last.data[0].get("date"):
            last_date = date.fromisoformat(resp_last.data[0]["date"][:10])
            start = max(season_start, last_date - timedelta(days=1))
        else:
            start = max(season_start, end - timedelta(days=7))
        log.info(f"[{season}]   Incremental: {start} → {end}")
    else:
        start = season_start
        log.info(f"[{season}]   Full scan: {start} → {end}")

    all_rows, skipped, cur = [], 0, start
    while cur <= end:
        date_rows = fetch_games_for_date(cur, season)
        new_rows  = [r for r in date_rows if r["game_id"] not in existing_ids]
        skipped  += len(date_rows) - len(new_rows)
        all_rows.extend(new_rows)
        if len(all_rows) >= 200:
            _upsert_game_rows(sb, all_rows)
            existing_ids.update(r["game_id"] for r in all_rows)
            all_rows = []
        cur += timedelta(days=1)
        time.sleep(0.15)

    if all_rows:
        _upsert_game_rows(sb, all_rows)

    log.info(f"[{season}]   ✓ Game history done. {skipped} skipped")
    log_refresh(sb, "game_history", 0, "success", season)

def _upsert_game_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("game_history").upsert(rows[i:i+100], on_conflict="season,game_id,team").execute()
    log.info(f"  Upserted {len(rows)} game rows")


# ── 3. Four Factors ───────────────────────────────────────────────────────────

def _parse_made_att(statistics: list, name: str) -> tuple:
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

def _stat(statistics: list, name: str):
    for s in statistics:
        if s.get("name") == name:
            try:
                return float(s["displayValue"])
            except (ValueError, KeyError):
                pass
    return None

def _has_real_data(statistics: list) -> bool:
    _, fga = _parse_made_att(statistics, "fieldGoalsMade-fieldGoalsAttempted")
    return fga is not None and fga > 0

def calc_four_factors(stats: list, opp_stats: list) -> dict:
    if not _has_real_data(stats) or not _has_real_data(opp_stats):
        return {k: None for k in ["efg_pct","tov_pct","orb_pct","ftr",
                                   "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]}
    fgm, fga   = _parse_made_att(stats, "fieldGoalsMade-fieldGoalsAttempted")
    tpm, _     = _parse_made_att(stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    _, fta     = _parse_made_att(stats, "freeThrowsMade-freeThrowsAttempted")
    tov = _stat(stats, "totalTurnovers") or 0.0
    orb = _stat(stats, "offensiveRebounds") or 0.0
    drb = _stat(stats, "defensiveRebounds") or 0.0
    fgm = fgm or 0.0; fga = fga or 0.0; tpm = tpm or 0.0; fta = fta or 0.0

    opp_fgm, opp_fga = _parse_made_att(opp_stats, "fieldGoalsMade-fieldGoalsAttempted")
    opp_tpm, _       = _parse_made_att(opp_stats, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    _, opp_fta       = _parse_made_att(opp_stats, "freeThrowsMade-freeThrowsAttempted")
    opp_tov = _stat(opp_stats, "totalTurnovers") or 0.0
    opp_orb = _stat(opp_stats, "offensiveRebounds") or 0.0
    opp_drb = _stat(opp_stats, "defensiveRebounds") or 0.0
    opp_fgm = opp_fgm or 0.0; opp_fga = opp_fga or 0.0
    opp_tpm = opp_tpm or 0.0; opp_fta = opp_fta or 0.0

    def safe(num, den):
        return round(num / den, 4) if den and den > 0 else None

    return {
        "efg_pct":     safe(fgm + 0.5 * tpm, fga),
        "tov_pct":     safe(tov, fga + 0.44 * fta + tov),
        "orb_pct":     safe(orb, orb + opp_drb),
        "ftr":         safe(fta, fga),
        "opp_efg_pct": safe(opp_fgm + 0.5 * opp_tpm, opp_fga),
        "opp_tov_pct": safe(opp_tov, opp_fga + 0.44 * opp_fta + opp_tov),
        "opp_orb_pct": safe(opp_orb, opp_orb + drb),
        "opp_ftr":     safe(opp_fta, opp_fga),
    }

def fetch_and_store_four_factors(sb: Client, season: int):
    log.info(f"[{season}] Fetching four factors…")
    resp = (sb.table("game_history").select("game_id,date,team,opponent")
              .eq("season", season).execute())
    if not resp.data:
        log.warning(f"[{season}]   No game history — skipping")
        return

    existing_adv = _get_all_ids(sb, "adv_game_history", season)
    all_game_ids = list({r["game_id"] for r in resp.data})
    new_game_ids = [gid for gid in all_game_ids if gid not in existing_adv]
    log.info(f"[{season}]   {len(existing_adv)} already have adv stats — fetching {len(new_game_ids)} new")

    if not new_game_ids:
        log.info(f"[{season}]   ✓ Nothing to fetch")
        _aggregate_four_factors_to_team_stats(sb, season)
        return

    game_meta = {r["game_id"]: r for r in resp.data if r["game_id"] not in {}}
    adv_rows, errors = [], 0

    for i, game_id in enumerate(new_game_ids):
        try:
            resp_s = requests.get(ESPN_SUMMARY, params={"event": game_id}, timeout=15)
            resp_s.raise_for_status()
            data = resp_s.json()
            box_teams = data.get("boxscore", {}).get("teams", [])
            if len(box_teams) < 2:
                continue
            team_stats_map = {bt["team"]["displayName"]: bt.get("statistics", []) for bt in box_teams}
            team_names = list(team_stats_map.keys())
            if len(team_names) < 2:
                continue
            t1, t2 = team_names[0], team_names[1]
            game_date = game_meta.get(game_id, {}).get("date", "")
            adv_rows.append({"season": season, "game_id": game_id, "date": game_date,
                             "team": t1, "opponent": t2,
                             **calc_four_factors(team_stats_map[t1], team_stats_map[t2])})
            adv_rows.append({"season": season, "game_id": game_id, "date": game_date,
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
            log.info(f"  Progress: {i}/{len(new_game_ids)}")
        time.sleep(0.2)

    if adv_rows:
        _upsert_adv_rows(sb, adv_rows)

    log.info(f"[{season}]   ✓ {len(new_game_ids) - errors} games stored, {errors} errors")
    log_refresh(sb, "adv_game_history", len(new_game_ids) - errors, "success", season)
    _aggregate_four_factors_to_team_stats(sb, season)

def _upsert_adv_rows(sb: Client, rows: list):
    for i in range(0, len(rows), 100):
        sb.table("adv_game_history").upsert(rows[i:i+100], on_conflict="season,game_id,team").execute()
    log.info(f"  Upserted {len(rows)} adv rows")

def _aggregate_four_factors_to_team_stats(sb: Client, season: int):
    log.info(f"[{season}]   Aggregating four factors…")
    all_rows, offset = [], 0
    while True:
        resp = (sb.table("adv_game_history").select("*").eq("season", season)
                  .range(offset, offset + SUPABASE_PAGE - 1).execute())
        all_rows.extend(resp.data)
        if len(resp.data) < SUPABASE_PAGE:
            break
        offset += SUPABASE_PAGE

    if not all_rows:
        log.warning(f"[{season}]   No adv data to aggregate")
        return

    df = pd.DataFrame(all_rows)
    ff_cols = ["efg_pct","tov_pct","orb_pct","ftr","opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"]
    for c in ff_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    avgs = df.groupby("team")[[c for c in ff_cols if c in df.columns]].mean().reset_index()
    ts_resp = sb.table("team_stats").select("team").eq("season", season).execute()
    bart_names = [r["team"] for r in ts_resp.data]

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
        import name_map as nm
        nm.build(bart_names, df["team"].unique().tolist())

        def find_bart(espn_name):
            espn_lower = str(espn_name).lower()
            bart = nm.to_bart(str(espn_name))
            if bart != espn_name and bart in bart_names:
                return bart
            if bart != espn_name:
                for c in [bart + ".", bart.rstrip(".")]:
                    if c in bart_names:
                        return c
            for b in bart_names:
                if nm.to_espn(b).lower() == espn_lower:
                    return b
            espn_clean = nm._clean(espn_name)
            for b in bart_names:
                if nm._clean(b) == espn_clean:
                    return b
            return None
    except Exception as e:
        log.warning(f"  name_map failed: {e}")
        def find_bart(espn_name): return None

    updated, skipped = 0, 0
    for _, row in avgs.iterrows():
        bart_name = find_bart(row["team"])
        if not bart_name:
            skipped += 1
            continue
        update = {c: round(float(row[c]), 4) for c in ff_cols if c in row and not pd.isna(row.get(c))}
        if update:
            sb.table("team_stats").update(update).eq("season", season).eq("team", bart_name).execute()
            updated += 1

    log.info(f"[{season}]   ✓ Updated {updated} teams ({skipped} unmatched)")
    log_refresh(sb, "four_factors", updated, "success", season)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NCAAB data pipeline")
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON,
                        help=f"Season year (default: {DEFAULT_SEASON})")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only fetch team stats, no ESPN calls")
    parser.add_argument("--skip-games", action="store_true",
                        help="Skip game history fetch")
    parser.add_argument("--skip-four-factors", action="store_true",
                        help="Skip four factors fetch")
    args = parser.parse_args()

    season = args.season
    log.info(f"=== NCAAB pipeline — season {season} ===")
    sb = get_supabase()

    fetch_and_store_team_stats(sb, season)
    if not args.stats_only:
        if not args.skip_games:
            fetch_and_store_game_history(sb, season)
        if not args.skip_four_factors:
            fetch_and_store_four_factors(sb, season)

    log.info(f"=== Pipeline complete — season {season} ===")