"""
pipeline/spot_check.py
======================
Sanity check four factors and efficiency rankings across seasons.
Run from the repo root:
    cd ~/Documents/ncaab_v2 && python3 pipeline/spot_check.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from pipeline.fetch_and_store import get_supabase

sb = get_supabase()

# ── Teams to check per season ─────────────────────────────────────────────────
# Format: {season: [(team_bart_name, expected_approx_rank)]}
CHECKS = {
    2015: [("Kentucky", 1), ("Duke", 2), ("Wisconsin", 3)],
    2016: [("Kansas", 1), ("Villanova", 3), ("Michigan St", 5)],
    2017: [("Gonzaga", 1), ("Kansas", 2), ("North Carolina", 4)],
    2018: [("Villanova", 1), ("Virginia", 2), ("Kansas", 3)],
    2019: [("Gonzaga", 1), ("Virginia", 2), ("Duke", 4)],
    2021: [("Gonzaga", 1), ("Baylor", 2), ("Michigan", 5)],
    2022: [("Gonzaga", 1), ("Arizona", 3), ("Kansas", 5)],
    2023: [("Houston", 2), ("Alabama", 1), ("Purdue", 4)],
    2024: [("Connecticut", 1), ("Houston", 2), ("Purdue", 3)],
    2025: [("Auburn", 1), ("Duke", 2), ("Florida", 3)],
    2026: [("Duke", 1), ("Auburn", 2), ("Houston", 3)],
}

FF_COLS = ["efg_pct", "tov_pct", "orb_pct", "ftr", "opp_efg_pct", "opp_tov_pct", "opp_orb_pct", "opp_ftr"]
EFF_COLS = ["adj_oe", "adj_de", "net_eff"]

# Expected sanity ranges for D1 basketball
RANGES = {
    "efg_pct":     (0.40, 0.65),
    "tov_pct":     (0.10, 0.25),
    "orb_pct":     (0.20, 0.45),
    "ftr":         (0.20, 0.55),
    "opp_efg_pct": (0.40, 0.65),
    "opp_tov_pct": (0.10, 0.25),
    "opp_orb_pct": (0.20, 0.45),
    "opp_ftr":     (0.20, 0.55),
    "adj_oe":      (85,  130),
    "adj_de":      (80,  115),
    "net_eff":     (-40,  45),
}

print("=" * 70)
print("NCAAB PROJECTOR — SPOT CHECK")
print("=" * 70)

total_checks = 0
total_warnings = 0

for season, teams in sorted(CHECKS.items()):
    print(f"\n── {season} ─────────────────────────────────────────")

    # Pull all teams for this season to compute rankings
    resp = sb.table("team_stats").select("*").eq("season", season).execute()
    rows = resp.data
    if not rows:
        print(f"  ⚠️  No data found for {season}")
        total_warnings += 1
        continue

    # Build net_eff ranking
    ranked = sorted(
        [r for r in rows if r.get("net_eff") is not None],
        key=lambda r: float(r["net_eff"]),
        reverse=True
    )
    rank_map = {r["team"]: i + 1 for i, r in enumerate(ranked)}

    for team, expected_rank in teams:
        row = next((r for r in rows if r["team"] == team), None)
        if not row:
            print(f"  ❌ {team}: NOT FOUND in team_stats")
            total_warnings += 1
            continue

        actual_rank = rank_map.get(team, "?")
        net = row.get("net_eff")
        adj_oe = row.get("adj_oe")
        adj_de = row.get("adj_de")

        # Check rank is roughly right (within 5 spots)
        rank_ok = isinstance(actual_rank, int) and abs(actual_rank - expected_rank) <= 5
        rank_flag = "✅" if rank_ok else "⚠️ "

        print(f"\n  {rank_flag} {team} (expected ~#{expected_rank}, actual #{actual_rank})")
        print(f"     Net Eff: {net:+.2f}  |  AdjOE: {adj_oe:.1f}  |  AdjDE: {adj_de:.1f}")

        if not rank_ok:
            total_warnings += 1

        # Check four factors in range
        warnings = []
        for col in FF_COLS + EFF_COLS:
            val = row.get(col)
            total_checks += 1
            if val is None:
                warnings.append(f"{col}=NULL")
                total_warnings += 1
            else:
                lo, hi = RANGES[col]
                if not (lo <= float(val) <= hi):
                    warnings.append(f"{col}={val:.4f} (expected {lo}–{hi})")
                    total_warnings += 1

        if warnings:
            print(f"     ⚠️  Out of range: {', '.join(warnings)}")
        else:
            print(f"     ✅ All four factors + efficiency in range")

print("\n" + "=" * 70)
print(f"SUMMARY: {total_warnings} warnings across {total_checks} checks")
if total_warnings == 0:
    print("✅ All good — data looks clean across seasons")
elif total_warnings <= 5:
    print("⚠️  Minor issues — review warnings above")
else:
    print("❌ Multiple issues found — investigate before proceeding")
print("=" * 70)