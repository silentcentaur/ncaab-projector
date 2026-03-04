import streamlit as st
import pandas as pd
import plotly.express as px
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
    st.markdown("# 🏀 Overview")
    st.markdown('<div class="tag">Season 2025–26</div><br>', unsafe_allow_html=True)

    df = db.get_team_data()
    if df.empty:
        st.warning("No data in database yet. Run the pipeline first.")
        return

    # Normalise column names (db returns lowercase)
    df.columns = [c.lower() for c in df.columns]

    num_teams   = len(df)
    top_offense = df.loc[df["adj_oe"].dropna().idxmax(), "team"]   if "adj_oe"  in df.columns else "—"
    top_defense = df.loc[df["adj_de"].dropna().idxmin(), "team"]   if "adj_de"  in df.columns else "—"
    top_net     = df.loc[df["net_eff"].dropna().idxmax(), "team"]  if "net_eff" in df.columns else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Teams",        num_teams)
    c2.metric("Best Offense", top_offense)
    c3.metric("Best Defense", top_defense)
    c4.metric("Top Net Eff.", top_net)

    st.markdown("<br>", unsafe_allow_html=True)

    if "adj_oe" in df.columns and "adj_de" in df.columns:
        st.markdown("### Offensive vs Defensive Efficiency")
        st.markdown('<div class="tag">All D1 Teams · Adjusted per 100 possessions</div><br>', unsafe_allow_html=True)
        fig = px.scatter(
            df, x="adj_oe", y="adj_de", hover_name="team",
            color="net_eff",
            color_continuous_scale=[[0,"#ef4444"],[0.5,"#fbbf24"],[1,"#22c55e"]],
            labels={"adj_oe":"Adj. Offensive Efficiency","adj_de":"Adj. Defensive Efficiency"},
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(marker=dict(size=7, opacity=0.85))
        med_oe = df["adj_oe"].median()
        med_de = df["adj_de"].median()
        for val, axis in [(med_oe,"x"),(med_de,"y")]:
            fig.add_shape(type="line",
                x0=val if axis=="x" else df["adj_oe"].min(),
                x1=val if axis=="x" else df["adj_oe"].max(),
                y0=val if axis=="y" else df["adj_de"].min(),
                y1=val if axis=="y" else df["adj_de"].max(),
                line=dict(color="#1e2d45", width=1, dash="dot"))
        fig.update_layout(**PLOT_THEME, height=480,
                          coloraxis_colorbar=dict(title="Net Eff."))
        st.plotly_chart(fig, width="stretch")

    if "net_eff" in df.columns:
        st.markdown("### Top 25 — Net Efficiency")
        top25 = df.nlargest(25, "net_eff").sort_values("net_eff")
        fig2 = go.Figure(go.Bar(
            x=top25["net_eff"], y=top25["team"], orientation="h",
            marker_color=["#f97316" if v>0 else "#ef4444" for v in top25["net_eff"]],
            text=top25["net_eff"].round(1), textposition="outside",
        ))
        fig2.update_layout(**PLOT_THEME, height=600,
                           xaxis_title="Net Efficiency (Adj OE − Adj DE)", yaxis_title="")
        st.plotly_chart(fig2, width="stretch")

    ff_cols = ["efg_pct","tov_pct","orb_pct","ftr"]
    if all(c in df.columns for c in ff_cols) and "net_eff" in df.columns:
        st.markdown("### Four Factors — Top 8 Teams")
        top8 = df.nlargest(8, "net_eff")
        categories = ["eFG%","TOV%","ORB%","FTR"]
        colors = ["#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa","#f43f5e","#84cc16","#fb923c"]
        fig3 = go.Figure()
        for i, (_, row) in enumerate(top8.iterrows()):
            vals = [
         	float(row["efg_pct"] or 0),
    		1 - float(row["tov_pct"] or 0),
    		float(row["orb_pct"] or 0),
    		float(row["ftr"] or 0),
            ]
            fig3.add_trace(go.Scatterpolar(
                r=vals+[vals[0]], theta=categories+[categories[0]],
                name=row["team"], line=dict(color=colors[i%len(colors)], width=2),
                fill="toself", fillcolor="rgba(249,115,22,0.1)",
            ))
        fig3.update_layout(**PLOT_THEME, height=450,
            polar=dict(bgcolor="rgba(0,0,0,0)",
                       radialaxis=dict(visible=True, gridcolor="#1e2d45", color="#64748b"),
                       angularaxis=dict(gridcolor="#1e2d45", color="#64748b")),
            legend=dict(font=dict(size=11)),
        )
        st.plotly_chart(fig3, width="stretch")
