import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

# Plot theme without xaxis/yaxis so individual charts can set their own
PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#f1f5f9",
    font_family="DM Sans",
)
GRID = dict(gridcolor="#1e2d45", zerolinecolor="#1e2d45")

CONF_COLORS = [
    "#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa",
    "#f43f5e","#84cc16","#fb923c","#38bdf8","#e879f9",
    "#4ade80","#facc15","#60a5fa","#f472b6","#34d399",
]

def rankings_html(df_top):
    medal = {1:"🥇",2:"🥈",3:"🥉"}
    html = '<div style="display:flex;flex-direction:column;gap:6px;">'
    for i, row in df_top.iterrows():
        team    = row.get("team","—")
        conf    = row.get("conference","")
        record  = row.get("record","")
        net     = row.get("net_eff")
        adj_oe  = row.get("adj_oe")
        adj_de  = row.get("adj_de")
        net_str = f"{net:+.1f}" if net is not None and not pd.isna(net) else "—"
        oe_str  = f"{adj_oe:.1f}" if adj_oe is not None and not pd.isna(adj_oe) else "—"
        de_str  = f"{adj_de:.1f}" if adj_de is not None and not pd.isna(adj_de) else "—"
        icon    = medal.get(i, f'<span style="color:#475569;font-size:0.8rem;">#{i}</span>')
        nc      = "#22c55e" if net and not pd.isna(net) and net > 0 else "#ef4444"
        html += f"""
        <div style="display:flex;align-items:center;background:#111827;border:1px solid #1e2d45;
                    border-radius:6px;padding:0.6rem 1rem;gap:1rem;">
            <div style="width:28px;text-align:center;font-size:1.1rem;">{icon}</div>
            <div style="flex:1;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;line-height:1.1;">{team}</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.65rem;color:#64748b;">{conf} · {record}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.2rem;color:{nc};">{net_str}</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:#475569;">NET EFF</div>
            </div>
            <div style="text-align:right;min-width:80px;">
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#94a3b8;">
                    <span style="color:#f97316;">{oe_str}</span> / <span style="color:#22c55e;">{de_str}</span>
                </div>
                <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:#475569;">OE / DE</div>
            </div>
        </div>"""
    html += '</div>'
    return html

def show():
    # Force dark background regardless of Streamlit theme setting
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"], section.main, .block-container,
    [data-testid="stMain"], .stMainBlockContainer {
        background-color: #0a0f1e !important;
        color: #f1f5f9 !important;
    }
    /* Fix plotly chart backgrounds in light mode */
    .js-plotly-plot .plotly .bg { fill: rgba(0,0,0,0) !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# 🏀 Overview")
    st.markdown('<div class="tag">Season 2025–26</div><br>', unsafe_allow_html=True)

    df      = db.get_team_data()
    game_df = db.get_game_history()

    if df.empty:
        st.warning("No data in database yet. Run the pipeline first.")
        return

    df.columns = [c.lower() for c in df.columns]

    # ── Summary metrics ───────────────────────────────────────────────────────
    total_teams = len(df)
    total_games = len(game_df) // 2 if not game_df.empty else 0
    top_team    = df.loc[df["net_eff"].dropna().idxmax(), "team"] if "net_eff" in df.columns else "—"
    top_conf    = df.groupby("conference")["net_eff"].mean().idxmax() if "conference" in df.columns else "—"

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("D1 Teams",       total_teams)
    c2.metric("Games Played",   total_games)
    c3.metric("#1 Team",        top_team)
    c4.metric("Top Conference", top_conf)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top 10 rankings cards ─────────────────────────────────────────────────
    st.markdown("### 🏆 Power Rankings")
    st.markdown('<div class="tag">Top 10 · Ranked by Net Efficiency</div><br>', unsafe_allow_html=True)

    if "net_eff" in df.columns:
        top10 = df.nlargest(10, "net_eff").reset_index(drop=True)
        top10.index = top10.index + 1
        st.markdown(rankings_html(top10), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Efficiency scatter ────────────────────────────────────────────────────
    st.markdown("### 📍 Efficiency Landscape")
    st.markdown('<div class="tag">Offense vs Defense · All D1 Teams</div><br>', unsafe_allow_html=True)

    if "adj_oe" in df.columns and "adj_de" in df.columns:
        from bracket_seeds import BRACKET_2026

        seed_map   = {}
        region_map = {}
        for region, seeds in BRACKET_2026.items():
            for seed, team in seeds.items():
                if team:
                    seed_map[team]   = seed
                    region_map[team] = region

        tourn_df = df[df["team"].isin(seed_map)].copy()
        tourn_df["seed"]     = tourn_df["team"].map(seed_map)
        tourn_df["region"]   = tourn_df["team"].map(region_map)
        tourn_df["seed_str"] = tourn_df["seed"].astype(str)

        SEED_COLORS = {
            1:  "#fbbf24", 2:  "#f97316", 3:  "#ef4444", 4:  "#e879f9",
            5:  "#a78bfa", 6:  "#60a5fa", 7:  "#38bdf8", 8:  "#34d399",
            9:  "#4ade80", 10: "#84cc16", 11: "#facc15", 12: "#fb923c",
            13: "#f472b6", 14: "#94a3b8", 15: "#64748b", 16: "#475569",
        }
        color_map = {str(s): SEED_COLORS[s] for s in range(1, 17)}

        fig = px.scatter(
            tourn_df, x="adj_oe", y="adj_de",
            hover_name="team", color="seed_str",
            color_discrete_map=color_map,
            text="team",
            hover_data={c: True for c in ["record","net_eff","region","seed"] if c in tourn_df.columns},
            labels={"adj_oe":"Adj. Offensive Efficiency","adj_de":"Adj. Defensive Efficiency","seed_str":"Seed"},
            category_orders={"seed_str": [str(s) for s in range(1, 17)]},
        )
        fig.update_yaxes(autorange="reversed", **GRID)
        fig.update_xaxes(**GRID)
        fig.update_traces(marker=dict(size=9, opacity=0.9), textposition="top center",
                          textfont=dict(size=8))

        med_oe = tourn_df["adj_oe"].median(); med_de = tourn_df["adj_de"].median()
        for val, axis in [(med_oe,"x"),(med_de,"y")]:
            fig.add_shape(type="line",
                x0=val if axis=="x" else tourn_df["adj_oe"].min(),
                x1=val if axis=="x" else tourn_df["adj_oe"].max(),
                y0=val if axis=="y" else tourn_df["adj_de"].min(),
                y1=val if axis=="y" else tourn_df["adj_de"].max(),
                line=dict(color="#1e2d45", width=1, dash="dot"))

        x_max=tourn_df["adj_oe"].max(); x_min=tourn_df["adj_oe"].min()
        y_max=tourn_df["adj_de"].max(); y_min=tourn_df["adj_de"].min()
        for text, x, y, anchor in [
            ("ELITE",        x_max-1, y_min+0.5, "right"),
            ("GOOD OFFENSE", x_max-1, y_max-0.5, "right"),
            ("GOOD DEFENSE", x_min+1, y_min+0.5, "left"),
            ("REBUILDING",   x_min+1, y_max-0.5, "left"),
        ]:
            fig.add_annotation(x=x, y=y, text=text, showarrow=False,
                               font=dict(size=9, color="#1e2d45"), xanchor=anchor)

        fig.update_layout(**PLOT_THEME, height=580,
                          legend=dict(title="Seed", font=dict(size=10), itemsizing="constant", bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#475569;margin-top:-0.5rem;">💡 Double-click a seed in the legend to isolate it</div><br>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Best offense vs best defense ──────────────────────────────────────────
    st.markdown("### ⚡ Best Offenses vs Best Defenses")
    off_col, def_col = st.columns(2)

    if "adj_oe" in df.columns:
        with off_col:
            st.markdown('<div class="tag orange">Top 10 Offenses</div><br>', unsafe_allow_html=True)
            top_off = df.nlargest(10, "adj_oe")[["team","adj_oe"]].sort_values("adj_oe")
            x_min_off = top_off["adj_oe"].min() - 1
            x_max_off = top_off["adj_oe"].max() + 3
            fig_off = go.Figure(go.Bar(
                x=top_off["adj_oe"], y=top_off["team"],
                orientation="h", marker_color="#f97316",
                text=top_off["adj_oe"].round(0).astype(int),
                textposition="outside",
                textfont=dict(color="#f1f5f9", size=11),
            ))
            fig_off.update_layout(
                **PLOT_THEME, height=340,
                xaxis=dict(range=[x_min_off, x_max_off], tickformat="d", **GRID),
                yaxis=dict(**GRID),
                xaxis_title="", yaxis_title="",
                margin=dict(l=0, r=50, t=10, b=10),
            )
            st.plotly_chart(fig_off, use_container_width=True)

    if "adj_de" in df.columns:
        with def_col:
            st.markdown('<div class="tag green">Top 10 Defenses</div><br>', unsafe_allow_html=True)
            top_def = df.nsmallest(10, "adj_de")[["team","adj_de"]].sort_values("adj_de", ascending=False)
            x_min_def = top_def["adj_de"].min() - 1
            x_max_def = top_def["adj_de"].max() + 3
            fig_def = go.Figure(go.Bar(
                x=top_def["adj_de"], y=top_def["team"],
                orientation="h", marker_color="#22c55e",
                text=top_def["adj_de"].round(0).astype(int),
                textposition="outside",
                textfont=dict(color="#f1f5f9", size=11),
            ))
            fig_def.update_layout(
                **PLOT_THEME, height=340,
                xaxis=dict(range=[x_min_def, x_max_def], tickformat="d", **GRID),
                yaxis=dict(**GRID),
                xaxis_title="", yaxis_title="",
                margin=dict(l=0, r=50, t=10, b=10),
            )
            st.plotly_chart(fig_def, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Conference strength ───────────────────────────────────────────────────
    st.markdown("### 🏛️ Conference Strength")
    st.markdown('<div class="tag">Average Net Efficiency · Min 6 teams</div><br>', unsafe_allow_html=True)

    if "conference" in df.columns and "net_eff" in df.columns:
        conf_df = (df.groupby("conference")
                     .agg(avg_net=("net_eff","mean"), teams=("team","count"))
                     .reset_index().query("teams >= 6")
                     .sort_values("avg_net", ascending=True))
        fig_conf = go.Figure(go.Bar(
            x=conf_df["avg_net"], y=conf_df["conference"],
            orientation="h",
            marker_color=["#f97316" if v > 0 else "#64748b" for v in conf_df["avg_net"]],
            text=conf_df["avg_net"].round(1), textposition="outside",
            textfont=dict(color="#f1f5f9"),
        ))
        fig_conf.update_layout(
            **PLOT_THEME, height=420,
            xaxis=dict(title="Avg. Net Efficiency", **GRID),
            yaxis=dict(**GRID),
            margin=dict(l=0, r=60, t=10, b=10),
        )
        st.plotly_chart(fig_conf, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Hottest teams ─────────────────────────────────────────────────────────
    if not game_df.empty and "team" in game_df.columns:
        st.markdown("### 🔥 Hottest Teams Right Now")
        st.markdown('<div class="tag">Best record in last 10 games · Min 8 played</div><br>', unsafe_allow_html=True)

        game_df.columns = [c.lower() for c in game_df.columns]
        game_df["date"] = pd.to_datetime(game_df["date"], errors="coerce")
        recent = game_df.sort_values("date", ascending=False).groupby("team").head(10)
        form = (recent.groupby("team")
                      .agg(wins=("result", lambda x: (x=="W").sum()), games=("result","count"))
                      .reset_index().query("games >= 8"))
        form["win_pct"] = form["wins"] / form["games"]
        form["record"]  = form["wins"].astype(str) + "-" + (form["games"]-form["wins"]).astype(str)
        form = form.sort_values("win_pct", ascending=False).head(10)
        if "conference" in df.columns:
            form = form.merge(df[["team","conference","net_eff"]], on="team", how="left")
        form_display = form[["team","record","win_pct"] +
                            [c for c in ["conference","net_eff"] if c in form.columns]]
        form_display = form_display.rename(columns={
            "team":"Team","record":"Last 10","win_pct":"Win%","conference":"Conf","net_eff":"Net Eff"})
        form_display["Win%"] = form_display["Win%"].round(3)
        if "Net Eff" in form_display.columns:
            form_display["Net Eff"] = pd.to_numeric(form_display["Net Eff"], errors="coerce").round(1)
        st.dataframe(form_display, use_container_width=True, hide_index=True,
                     column_config={
                         "Win%":    st.column_config.NumberColumn("Win%",    format="%.0%"),
                         "Net Eff": st.column_config.NumberColumn("Net Eff", format="%+.1f"),
                     })