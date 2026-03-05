import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#f1f5f9", font_family="DM Sans",
)
GRID = dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45")

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# 📈 Game Log")

    game_df = db.get_game_history()
    team_df = db.get_team_data()

    if game_df.empty:
        st.warning("No game log data in database yet. Run the pipeline first.")
        return

    game_df.columns = [c.lower() for c in game_df.columns]
    if not team_df.empty:
        team_df.columns = [c.lower() for c in team_df.columns]

    # Use ESPN full team names from game history
    game_teams = sorted(game_df["team"].dropna().unique().tolist())

    f1, f2, f3 = st.columns(3)
    sel_team   = f1.selectbox("Team", ["All"] + game_teams, index=None, placeholder="Type to search...")
    if sel_team is None:
        sel_team = "All"

    venue_opts = ["All"] + sorted(game_df["venue"].dropna().unique().tolist()) if "venue" in game_df.columns else ["All"]
    sel_venue  = f2.selectbox("Venue",  venue_opts)
    sel_result = f3.selectbox("Result", ["All", "W", "L"])

    filt = game_df.copy()
    if sel_team   != "All": filt = filt[filt["team"]   == sel_team]
    if sel_venue  != "All": filt = filt[filt["venue"]  == sel_venue]
    if sel_result != "All": filt = filt[filt["result"] == sel_result]

    filt["date"]           = pd.to_datetime(filt["date"], errors="coerce")
    filt["points_for"]     = pd.to_numeric(filt["points_for"],     errors="coerce")
    filt["points_against"] = pd.to_numeric(filt["points_against"], errors="coerce")
    filt["margin"]         = filt["points_for"] - filt["points_against"]
    filt = filt.sort_values("date", ascending=False)

    # ── Enrich with opponent net efficiency ───────────────────────────────────
    if not team_df.empty and "team" in team_df.columns and "net_eff" in team_df.columns:
        # Build a lookup: ESPN full name → net_eff
        # team_df uses BartTorvik short names, so we do a fuzzy match on first word
        opp_lookup = {}
        for _, tr in team_df.iterrows():
            short = str(tr["team"]).lower().strip()
            opp_lookup[short] = tr["net_eff"]

        def match_net_eff(espn_name):
            if pd.isna(espn_name): return None
            # Try exact match first (lowercased)
            key = str(espn_name).lower().strip()
            if key in opp_lookup: return opp_lookup[key]
            # Try matching on first word of ESPN name
            first = key.split()[0] if key else ""
            for k, v in opp_lookup.items():
                if k.startswith(first): return v
            return None

        filt["opp_net_eff"] = filt["opponent"].apply(match_net_eff)
        filt["opp_net_eff"] = pd.to_numeric(filt["opp_net_eff"], errors="coerce")

        # Difficulty tier
        def difficulty(ne):
            if ne is None or pd.isna(ne): return "—"
            if ne >= 15:  return "🔴 Elite"
            if ne >= 8:   return "🟠 Strong"
            if ne >= 2:   return "🟡 Average"
            if ne >= -5:  return "🟢 Below Avg"
            return "⚪ Weak"
        filt["opp_difficulty"] = filt["opp_net_eff"].apply(difficulty)
    else:
        filt["opp_net_eff"]    = None
        filt["opp_difficulty"] = "—"

    if not filt.empty:
        w      = (filt["result"] == "W").sum()
        l      = (filt["result"] == "L").sum()
        avg_pf = filt["points_for"].mean()
        avg_pa = filt["points_against"].mean()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Record",             f"{w}–{l}")
        m2.metric("Avg Points For",     f"{avg_pf:.1f}" if not pd.isna(avg_pf) else "—")
        m3.metric("Avg Points Against", f"{avg_pa:.1f}" if not pd.isna(avg_pa) else "—")
        m4.metric("Avg Margin",         f"{avg_pf-avg_pa:+.1f}" if not pd.isna(avg_pf) else "—")

        st.markdown("<br>", unsafe_allow_html=True)

        if sel_team != "All":
            pd2    = filt.sort_values("date").copy()
            labels = (pd2["date"].dt.strftime("%m/%d") + " vs " + pd2["opponent"].fillna("")).tolist()
            shared_x = list(range(len(pd2)))  # numeric index so both charts share same width

            # ── Point Margin chart ────────────────────────────────────────────
            st.markdown("### Point Margin by Game")
            margins = pd2["margin"].tolist()
            m_max   = max(abs(pd2["margin"].max()), abs(pd2["margin"].min()), 5)
            y_range = [-m_max * 1.3, m_max * 1.3]

            fig = go.Figure()
            fig.add_hline(y=0, line=dict(color="#334155", width=1))
            fig.add_bar(
                x=shared_x, y=margins,
                marker_color=["#22c55e" if m > 0 else "#ef4444" for m in margins],
                text=[f"{'+' if m>0 else ''}{m:.0f}" for m in margins],
                textposition="outside",
                textfont=dict(size=9, color="#94a3b8"),
            )
            fig.update_layout(
                **PLOT_THEME, height=300, bargap=0.2,
                xaxis=dict(tickmode="array", tickvals=shared_x, ticktext=labels,
                           tickangle=-45, tickfont=dict(size=9), **GRID),
                yaxis=dict(range=y_range, **GRID),
                margin=dict(l=10, r=10, t=10, b=120),
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Rolling avg chart ─────────────────────────────────────────────
            if len(pd2) >= 5:
                st.markdown("### Rolling 5-Game Avg")
                pd2["roll_pf"] = pd2["points_for"].rolling(5, min_periods=1).mean()
                pd2["roll_pa"] = pd2["points_against"].rolling(5, min_periods=1).mean()

                all_pts  = pd.concat([pd2["roll_pf"], pd2["roll_pa"]]).dropna()
                pt_min   = all_pts.min() - 5
                pt_max   = all_pts.max() + 5

                fig2 = go.Figure()
                fig2.add_scatter(x=shared_x, y=pd2["roll_pf"].tolist(), name="Pts For",
                                 line=dict(color="#f97316", width=2),
                                 mode="lines+markers", marker=dict(size=5))
                fig2.add_scatter(x=shared_x, y=pd2["roll_pa"].tolist(), name="Pts Against",
                                 line=dict(color="#ef4444", width=2, dash="dot"),
                                 mode="lines+markers", marker=dict(size=5))
                fig2.update_layout(
                    **PLOT_THEME, height=300,
                    xaxis=dict(tickmode="array", tickvals=shared_x, ticktext=labels,
                               tickangle=-45, tickfont=dict(size=9), **GRID),
                    yaxis=dict(range=[pt_min, pt_max], **GRID),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=10, r=10, t=10, b=120),
                )
                st.plotly_chart(fig2, use_container_width=True)

    # ── Game log table ────────────────────────────────────────────────────────
    st.markdown("### Game Log Table")
    display_cols = [c for c in ["date","team","opponent","opp_difficulty","opp_net_eff",
                                "venue","points_for","points_against","margin","result"]
                    if c in filt.columns]
    st.dataframe(
        filt[display_cols].head(200).reset_index(drop=True),
        use_container_width=True, hide_index=True,
        column_config={
            "margin":       st.column_config.NumberColumn("Margin",      format="%+.0f"),
            "opp_net_eff":  st.column_config.NumberColumn("Opp Net Eff", format="%+.1f"),
            "opp_difficulty": st.column_config.TextColumn("Difficulty"),
        }
    )