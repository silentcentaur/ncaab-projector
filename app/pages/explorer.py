import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#f1f5f9", font_family="DM Sans",
    xaxis=dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45"),
    yaxis=dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45"),
)

def percentile_rank(series, value, higher_is_better=True):
    s = series.dropna()
    if s.empty: return 50.0
    pct = (s < value).sum() / len(s) * 100
    return pct if higher_is_better else 100 - pct

def show(season: int):
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# 📊 Team Explorer")

    df      = db.get_team_data(season)
    teams   = db.team_list(season)
    game_df = db.get_game_history(season)

    if df.empty or not teams:
        st.warning("No data in database yet. Run the pipeline first.")
        return

    df.columns = [c.lower() for c in df.columns]

    selected = st.selectbox("Select a team", teams, index=None, placeholder="Type to search...")
    if not selected:
        st.markdown("""
        <div style="margin-top:4rem;text-align:center;padding:3rem;border:1px dashed #1e2d45;border-radius:8px;">
            <div style="font-size:2rem;color:#334155;font-weight:700;">SELECT A TEAM TO BEGIN</div>
            <div style="font-size:0.8rem;color:#334155;margin-top:0.5rem;">Type a team name in the box above</div>
        </div>""", unsafe_allow_html=True)
        return

    row = df[df["team"] == selected]
    if row.empty:
        st.error("Team not found.")
        return
    row = row.iloc[0]

    conf    = row.get("conference", "—")
    record  = row.get("record", "—")
    net_eff = row.get("net_eff")
    net_eff_ok = net_eff is not None and not pd.isna(net_eff)
    rank = int(df["net_eff"].rank(ascending=False)[df["team"]==selected].values[0]) if "net_eff" in df.columns else "—"

    st.markdown(f"""
    <div class="matchup-banner">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:2.8rem;letter-spacing:0.05em;">{selected}</div>
        <div style="display:flex;gap:0.5rem;justify-content:center;margin-top:0.5rem;flex-wrap:wrap;">
            <span class="tag">{conf}</span>
            <span class="tag orange">{record}</span>
            <span class="tag {'green' if net_eff_ok and net_eff > 0 else 'red'}">
                NET EFF: {f'{net_eff:+.1f}' if net_eff_ok else '—'}
            </span>
            <span class="tag">Rank #{rank}</span>
        </div>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    def m(col, c, fmt=".1f", invert=False):
        val = row.get(col)
        if val is not None and not pd.isna(val):
            pct   = percentile_rank(df[col], val, not invert) if col in df.columns else None
            delta = f"P{int(pct)}" if pct else None
            c.metric(col.replace("_"," ").title(), f"{val:{fmt}}", delta)
        else:
            c.metric(col.replace("_"," ").title(), "—")
    m("adj_oe", c1); m("adj_de", c2, invert=True); m("adj_tempo", c3)
    m("efg_pct", c4, fmt=".3f"); m("tov_pct", c5, fmt=".3f", invert=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Season Profile vs. National Percentiles")

    radar_stats = {
        "Off. Eff.": ("adj_oe",True), "Def. Eff.": ("adj_de",False),
        "Tempo": ("adj_tempo",True), "eFG%": ("efg_pct",True),
        "Opp eFG%": ("opp_efg_pct",False), "ORB%": ("orb_pct",True),
        "TOV%": ("tov_pct",False), "FTR": ("ftr",True),
    }
    labels, pcts = [], []
    for lbl,(col,hib) in radar_stats.items():
        val = row.get(col)
        if col in df.columns and val is not None and not pd.isna(val):
            labels.append(lbl); pcts.append(percentile_rank(df[col], val, hib))

    if labels:
        fig = go.Figure(go.Scatterpolar(
            r=pcts+[pcts[0]], theta=labels+[labels[0]],
            fill="toself", fillcolor="rgba(249,115,22,0.15)",
            line=dict(color="#f97316", width=2), name=selected,
        ))
        fig.update_layout(**PLOT_THEME, height=380,
            polar=dict(bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True,range=[0,100],gridcolor="#1e2d45",color="#64748b",ticksuffix="%"),
                angularaxis=dict(gridcolor="#1e2d45",color="#94a3b8")))
        st.plotly_chart(fig, use_container_width=True)

    if not game_df.empty and "team" in game_df.columns:
        tg = nm.get_team_games(game_df, df, selected)
        if not tg.empty:
            st.markdown("### Game Log")
            tg["date"]   = pd.to_datetime(tg["date"], errors="coerce")
            tg           = tg.sort_values("date", ascending=False)
            tg["margin"] = pd.to_numeric(tg["points_for"],errors="coerce") - \
                           pd.to_numeric(tg["points_against"],errors="coerce")
            fig2 = go.Figure()
            fig2.add_hline(y=0, line=dict(color="#1e2d45",width=1))
            fig2.add_bar(
                x=tg["date"].dt.strftime("%m/%d").tolist()[::-1],
                y=tg["margin"].tolist()[::-1],
                marker_color=["#22c55e" if v>0 else "#ef4444" for v in tg["margin"].tolist()[::-1]],
            )
            fig2.update_layout(**PLOT_THEME, height=260,
                               xaxis_title="Date", yaxis_title="Point Margin", bargap=0.15)
            st.plotly_chart(fig2, use_container_width=True)
            cols = [c for c in ["date","opponent","venue","points_for","points_against","margin","result"] if c in tg.columns]
            st.dataframe(tg[cols].head(30), use_container_width=True, hide_index=True)

    with st.expander("All Season Stats"):
        st.dataframe(pd.DataFrame(row).T, use_container_width=True, hide_index=True)