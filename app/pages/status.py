import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

def show():
    st.markdown("# 🔄 Data Status")
    st.markdown('<div class="tag">Powered by Supabase + GitHub Actions nightly job</div><br>', unsafe_allow_html=True)

    # ── Last refresh times ────────────────────────────────────────────────────
    st.markdown("### Last Refresh")
    log_df = db.get_refresh_log()

    if log_df.empty:
        st.info("No refresh history yet. Run the pipeline to populate data.")
    else:
        log_df.columns = [c.lower() for c in log_df.columns]
        latest = log_df.groupby("data_type").first().reset_index()

        cols = st.columns(3)
        for i, data_type in enumerate(["team_stats","game_history","adv_game_history"]):
            row = latest[latest["data_type"]==data_type]
            label = {"team_stats":"Team Stats","game_history":"Game History","adv_game_history":"Adv. History"}[data_type]
            if row.empty:
                cols[i].markdown(f"""
                <div class="stat-card">
                    <div class="label">{label}</div>
                    <div style="color:#64748b;font-size:0.85rem;margin-top:4px;">Not yet fetched</div>
                </div>""", unsafe_allow_html=True)
            else:
                r       = row.iloc[0]
                status  = r.get("status","—")
                rows_up = r.get("rows_upserted","—")
                ran_at  = r.get("ran_at","—")
                color   = "#22c55e" if status=="success" else "#ef4444"
                cols[i].markdown(f"""
                <div class="stat-card">
                    <div class="label">{label}</div>
                    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:{color};margin-top:4px;">
                        {status.upper()}
                    </div>
                    <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;margin-top:4px;">
                        {rows_up} rows · {str(ran_at)[:16]}
                    </div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Full refresh log ──────────────────────────────────────────────────────
    if not log_df.empty:
        with st.expander("Full Refresh Log"):
            st.dataframe(log_df, width="stretch", hide_index=True)

    # ── Manual cache clear ────────────────────────────────────────────────────
    st.markdown("### Cache")
    st.markdown("""
    <div class="stat-card">
        <div class="label">Query Cache</div>
        <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px;">
            The app caches Supabase queries for 5 minutes to keep things fast.
            If you've just run the pipeline and want to see fresh data immediately, clear the cache below.
        </div>
    </div>""", unsafe_allow_html=True)

    if st.button("Clear Cache"):
        db.clear_cache()
        st.success("Cache cleared — next page load will fetch fresh data from Supabase.")

    # ── Architecture info ─────────────────────────────────────────────────────
    with st.expander("⚙️  How the data pipeline works"):
        st.markdown("""
        **Data flow:**
        ```
        BartTorvik (CSV)  ──┐
                            ├──▶  pipeline/fetch_and_store.py  ──▶  Supabase DB
        ESPN via cbbpy   ──┘
                                         ↑
                              GitHub Actions runs this
                              every night at 2am EST
                                         ↓
                              This Streamlit app reads
                              from Supabase on demand
        ```

        **To trigger a manual refresh:**
        1. Go to your GitHub repo
        2. Click **Actions** → **Nightly NCAAB Data Refresh**
        3. Click **Run workflow**

        **To update the season year:**
        Edit `SEASON = 2026` in both `pipeline/fetch_and_store.py` and `app/db.py`
        """)
