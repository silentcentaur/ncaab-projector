import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from dotenv import load_dotenv
load_dotenv()
from fetch_and_store import get_supabase, _aggregate_four_factors_to_team_stats

sb = get_supabase()
_aggregate_four_factors_to_team_stats(sb)
