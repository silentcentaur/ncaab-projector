import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#f1f5f9", font_family="DM Sans",
    xaxis=dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45"),
    yaxis=dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45"),
)

def show():
    st.markdown("# 📈 Game Log")
    game_df = db.get_game_history()
    adv_df  = db.get_adv_history()
    teams   = db.team_list()

    if game_df.empty:
        st.warning("No game log data in database yet. Run the pipeline first.")
        return

    game_df.columns = [c.lower() for c in game_df.columns]

    f1,f2,f3 = st.columns(3)
    sel_team   = f1.selectbox("Team",   ["All"]+teams)
    venue_opts = ["All"]+sorted(game_df["venue"].dropna().unique().tolist())   if "venue"  in game_df.columns else ["All"]
    sel_venue  = f2.selectbox("Venue",  venue_opts)
    sel_result = f3.selectbox("Result", ["All","W","L"])

    filt = game_df.copy()
    if sel_team   != "All": filt = filt[filt["team"]   == sel_team]
    if sel_venue  != "All": filt = filt[filt["venue"]  == sel_venue]
    if sel_result != "All": filt = filt[filt["result"] == sel_result]

    filt["date"]           = pd.to_datetime(filt["date"], errors="coerce")
    filt["points_for"]     = pd.to_numeric(filt["points_for"],     errors="coerce")
    filt["points_against"] = pd.to_numeric(filt["points_against"], errors="coerce")
    filt["margin"]         = filt["points_for"] - filt["points_against"]
    filt = filt.sort_values("date", ascending=False)

    if not filt.empty:
        w=( filt["result"]=="W").sum(); l=(filt["result"]=="L").sum()
        avg_pf=filt["points_for"].mean(); avg_pa=filt["points_against"].mean()
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Record", f"{w}–{l}")
        m2.metric("Avg Points For",     f"{avg_pf:.1f}" if not pd.isna(avg_pf) else "—")
        m3.metric("Avg Points Against", f"{avg_pa:.1f}" if not pd.isna(avg_pa) else "—")
        m4.metric("Avg Margin",         f"{avg_pf-avg_pa:+.1f}" if not pd.isna(avg_pf) else "—")

        st.markdown("<br>", unsafe_allow_html=True)

        if sel_team != "All":
            st.markdown("### Point Margin by Game")
            pd2 = filt.sort_values("date")
            pd2["label"] = pd2["date"].dt.strftime("%m/%d")+" vs "+pd2["opponent"].fillna("")
            fig = go.Figure()
            fig.add_hline(y=0, line=dict(color="#334155",width=1))
            fig.add_bar(x=pd2["label"], y=pd2["margin"],
                        marker_color=["#22c55e" if m>0 else "#ef4444" for m in pd2["margin"]])
            fig.update_layout(**PLOT_THEME, height=280, xaxis_tickangle=-45, bargap=0.2)
            st.plotly_chart(fig, width="stretch")

            if len(pd2) >= 5:
                st.markdown("### Rolling 5-Game Avg")
                pd2["roll_pf"] = pd2["points_for"].rolling(5,min_periods=1).mean()
                pd2["roll_pa"] = pd2["points_against"].rolling(5,min_periods=1).mean()
                fig2 = go.Figure()
                fig2.add_scatter(x=pd2["label"],y=pd2["roll_pf"],name="Pts For",
                                 line=dict(color="#f97316",width=2))
                fig2.add_scatter(x=pd2["label"],y=pd2["roll_pa"],name="Pts Against",
                                 line=dict(color="#ef4444",width=2,dash="dot"))
                fig2.update_layout(**PLOT_THEME, height=280, xaxis_tickangle=-45)
                st.plotly_chart(fig2, width="stretch")

    if not adv_df.empty:
        adv_df.columns = [c.lower() for c in adv_df.columns]
        adv_filt = adv_df[adv_df["team"]==sel_team].copy() if sel_team != "All" else adv_df.copy()
        if not adv_filt.empty:
            st.markdown("### Advanced Four Factors by Game")
            ff = [c for c in ["efg_pct","tov_pct","orb_pct","ftr","opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ftr"] if c in adv_filt.columns]
            st.dataframe(adv_filt[["date","team","opponent"]+ff].head(50), width="stretch", hide_index=True)

    st.markdown("### Game Log Table")
    cols = [c for c in ["date","team","opponent","venue","points_for","points_against","margin","result"] if c in filt.columns]
    st.dataframe(filt[cols].head(200).reset_index(drop=True), width="stretch", hide_index=True,
                 column_config={"margin": st.column_config.NumberColumn("Margin", format="%+.0f")})
