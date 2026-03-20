"""
pipeline/debug_check.py
=======================
Targeted debug for:
1. Michigan St name in 2016 team_stats
2. Auburn 2026 ranking anomaly

Run: cd ~/Documents/ncaab_v2 && python3 pipeline/debug_check.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from pipeline.fetch_and_store import get_supabase

sb = get_supabase()

# ── 1. Michigan St in 2016 ────────────────────────────────────────────────────
print("=" * 60)
print("1. MICHIGAN ST — 2016 team_stats name search")
print("=" * 60)

resp = sb.table("team_stats").select("team,net_eff,adj_oe,adj_de").eq("season", 2016).execute()
teams_2016 = [r["team"] for r in resp.data]

# Search for anything Michigan-related
mich = [t for t in teams_2016 if "mich" in t.lower()]
print(f"Teams with 'mich' in name: {mich}")

# Also show top 20 by net_eff so we can see where they rank
ranked = sorted(resp.data, key=lambda r: float(r["net_eff"] or 0), reverse=True)
print("\nTop 20 teams by net_eff in 2016:")
for i, r in enumerate(ranked[:20], 1):
    print(f"  #{i:2d}  {r['team']:<30} net={float(r['net_eff']):+.2f}  OE={r['adj_oe']:.1f}  DE={r['adj_de']:.1f}")

# ── 2. Auburn 2026 ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. AUBURN — 2026 team_stats raw row")
print("=" * 60)

resp2 = sb.table("team_stats").select("*").eq("season", 2026).eq("team", "Auburn").execute()
if resp2.data:
    row = resp2.data[0]
    for k, v in sorted(row.items()):
        print(f"  {k:<20} {v}")
else:
    print("  Auburn not found in 2026 team_stats")

# Show top 10 for 2026 context
print("\nTop 10 teams by net_eff in 2026:")
resp3 = sb.table("team_stats").select("team,net_eff,adj_oe,adj_de,record").eq("season", 2026).execute()
ranked3 = sorted(resp3.data, key=lambda r: float(r["net_eff"] or 0), reverse=True)
for i, r in enumerate(ranked3[:10], 1):
    print(f"  #{i:2d}  {r['team']:<30} net={float(r['net_eff']):+.2f}  OE={r['adj_oe']:.1f}  DE={r['adj_de']:.1f}  {r['record']}")

# Check Auburn's game history for 2026 — how many games?
print("\nAuburn 2026 game_history count:")
resp4 = sb.table("game_history").select("game_id,date,result,points_for,points_against").eq("season", 2026).eq("team", "Auburn").execute()
print(f"  {len(resp4.data)} games found")
if resp4.data:
    import pandas as pd
    gdf = pd.DataFrame(resp4.data)
    gdf["date"] = pd.to_datetime(gdf["date"])
    gdf = gdf.sort_values("date", ascending=False)
    print(f"  Most recent: {gdf.iloc[0]['date'].date()}  {gdf.iloc[0]['result']}  {gdf.iloc[0]['points_for']}-{gdf.iloc[0]['points_against']}")
    print(f"  Record: {(gdf['result']=='W').sum()}-{(gdf['result']=='L').sum()}")