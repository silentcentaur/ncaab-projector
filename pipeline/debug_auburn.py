"""
pipeline/debug_auburn.py
========================
Check what name Auburn is stored under in game_history for 2026.
Run: cd ~/Documents/ncaab_v2 && python3 pipeline/debug_auburn.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from pipeline.fetch_and_store import get_supabase

sb = get_supabase()

# Search game_history for anything Auburn-related
print("Searching game_history 2026 for 'auburn'...")
resp = sb.table("game_history").select("team,opponent,date,result").eq("season", 2026).ilike("team", "%auburn%").limit(5).execute()
print(f"  As 'team': {[r['team'] for r in resp.data]}")

resp2 = sb.table("game_history").select("team,opponent,date,result").eq("season", 2026).ilike("opponent", "%auburn%").limit(5).execute()
print(f"  As 'opponent': {[r['opponent'] for r in resp2.data][:3]}")

# Also check what the BartTorvik CSV has for Auburn 2026 right now
import requests
from io import StringIO
import pandas as pd

print("\nChecking BartTorvik CSV for Auburn 2026...")
url = "https://barttorvik.com/2026_team_results.csv"
resp3 = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
df = pd.read_csv(StringIO(resp3.text), header=0)
df.columns = [c.strip().lower() for c in df.columns]
auburn_row = df[df.iloc[:, 0].astype(str).str.lower().str.contains("auburn")]
if auburn_row.empty:
    # Try second column in case of shifted columns
    auburn_row = df[df.iloc[:, 1].astype(str).str.lower().str.contains("auburn")]
print(f"  Auburn rows found: {len(auburn_row)}")
if not auburn_row.empty:
    print(auburn_row.to_string())