"""
app/db.py
=========
Fetches data from Supabase for the Streamlit UI.
All queries are cached with st.cache_data (5 min TTL).
"""

import os
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SEASON = 2026
PAGE   = 1000   # Supabase default row limit

@st.cache_resource
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(url, key)


def _paginate(sb: Client, table: str, season: int) -> list:
    """Fetch ALL rows from a table, paginating past Supabase's 1000-row limit."""
    all_rows = []
    offset = 0
    while True:
        resp = (sb.table(table)
                  .select("*")
                  .eq("season", season)
                  .range(offset, offset + PAGE - 1)
                  .execute())
        all_rows.extend(resp.data)
        if len(resp.data) < PAGE:
            break
        offset += PAGE
    return all_rows


@st.cache_data(ttl=300)
def get_team_data() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("team_stats").select("*").eq("season", SEASON).execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return df
    if "adj_oe" in df.columns and "adj_de" in df.columns:
        df["net_eff"] = df["adj_oe"] - df["adj_de"]
    return df.sort_values("team").reset_index(drop=True)


@st.cache_data(ttl=300)
def get_game_history() -> pd.DataFrame:
    sb = get_client()
    return pd.DataFrame(_paginate(sb, "game_history", SEASON))


@st.cache_data(ttl=300)
def get_adv_history() -> pd.DataFrame:
    sb = get_client()
    return pd.DataFrame(_paginate(sb, "adv_game_history", SEASON))


@st.cache_data(ttl=300)
def get_refresh_log() -> pd.DataFrame:
    sb = get_client()
    resp = (sb.table("refresh_log")
              .select("*")
              .order("ran_at", desc=True)
              .limit(20)
              .execute())
    return pd.DataFrame(resp.data)


def team_list() -> list[str]:
    df = get_team_data()
    if df.empty or "team" not in df.columns:
        return []
    return sorted(df["team"].dropna().tolist())


def clear_cache():
    get_team_data.clear()
    get_game_history.clear()
    get_adv_history.clear()
    get_refresh_log.clear()