"""
pipeline/check_name_mapping.py
===============================
Diagnostic script: checks every ESPN team name in game_history against
the BartTorvik team list and reports any that wouldn't match in the UI.

Run from the pipeline directory:
    python check_name_mapping.py

Output:
  - Teams with no match (games are invisible in UI)
  - Teams with ambiguous/partial matches
  - Summary stats
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from dotenv import load_dotenv
load_dotenv()

from fetch_and_store import get_supabase
import name_map as nm

def main():
    sb = get_supabase()

    # Load all ESPN team names from game_history
    print("Loading game_history...")
    resp = sb.table("game_history").select("team").eq("season", 2026).execute()
    espn_names = sorted(set(r["team"] for r in resp.data if r.get("team")))

    # Load all BartTorvik team names from team_stats
    print("Loading team_stats...")
    resp2 = sb.table("team_stats").select("team").eq("season", 2026).execute()
    bart_names = sorted(set(r["team"] for r in resp2.data if r.get("team")))

    print(f"\n  ESPN unique teams in game_history: {len(espn_names)}")
    print(f"  BartTorvik teams in team_stats:    {len(bart_names)}")

    # Build the name map
    nm.build(bart_names, espn_names)

    # Check every ESPN name: can we map it back to a BartTorvik name?
    no_match    = []
    matched     = []

    for espn in espn_names:
        bart = nm.to_bart(espn)
        if bart == espn:
            # to_bart returned the input unchanged = no match found
            # Double-check: is there a BartTorvik name that maps TO this ESPN name?
            found = any(nm.to_espn(b) == espn for b in bart_names)
            if not found:
                no_match.append(espn)
            else:
                matched.append((espn, bart))
        else:
            matched.append((espn, bart))

    print(f"\n{'='*60}")
    print(f"  MATCHED:    {len(matched)} ESPN teams map correctly to BartTorvik")
    print(f"  NO MATCH:   {len(no_match)} ESPN teams have NO BartTorvik equivalent")
    print(f"{'='*60}")

    if no_match:
        # Count how many games are affected
        resp3 = (sb.table("game_history")
                   .select("team")
                   .eq("season", 2026)
                   .execute())
        game_counts = {}
        for r in resp3.data:
            t = r["team"]
            game_counts[t] = game_counts.get(t, 0) + 1

        print(f"\n⚠️  Teams with NO match ({len(no_match)} teams):")
        print(f"   These teams' games ARE in the DB but won't show in the UI.\n")

        # Sort by game count descending so most impactful are first
        no_match_sorted = sorted(no_match, key=lambda t: game_counts.get(t, 0), reverse=True)
        for espn in no_match_sorted:
            count = game_counts.get(espn, 0)
            print(f"   {count:3d} games  |  {espn}")

        print(f"\n   To fix: add these to the MANUAL dict in app/name_map.py")
        print(f"   Format: \"BartTorvik name\": \"{no_match_sorted[0]}\",")
    else:
        print("\n✅ All ESPN team names match a BartTorvik team. No issues found!")

    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()