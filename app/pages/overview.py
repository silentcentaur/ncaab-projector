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

CONF_COLORS = [
    "#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa",
    "#f43f5e","#84cc16","#fb923c","#38bdf8","#e879f9",
    "#4ade80","#facc15","#60a5fa","#f472b6","#34d399",
]

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)

    st.markdown("# 🏀 Overview")
    st.markdown('<div class="tag">Season 2025–26</div><br>', unsafe_allow_html=True)

    df      = db.get_team_data()
    game_df = db.get_game_history()

    if df.empty:
        st.warning("No data in database yet. Run the pipeline first.")
        return

    df.columns = [c.lower() for c in df.columns]

    # ── Top summary metrics ───────────────────────────────────────────────────
    total_teams = len(df)
    total_games = len(game_df) // 2 if not game_df.empty else 0
    top_team    = df.loc[df["net_eff"].dropna().idxmax(), "team"] if "net_eff" in df.columns else "—"
    top_conf    = df.groupby("conference")["net_eff"].mean().idxmax() if "conference" in df.columns else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("D1 Teams",     total_teams)
    c2.metric("Games Played", total_games)
    c3.metric("#1 Team",      top_team)
    c4.metric("Top Conference", top_conf)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top 25 leaderboard ────────────────────────────────────────────────────
    st.markdown("### 🏆 Top 25 Power Rankings")
    st.markdown('<div class="tag">Ranked by Net Efficiency · Adjusted per 100 possessions</div><br>', unsafe_allow_html=True)

    if "net_eff" in df.columns:
        top25 = df.nlargest(25, "net_eff").reset_index(drop=True)
        top25.index += 1

        display_cols = {
            "team":      "Team",
            "conference":"Conf",
            "record":    "Record",
            "adj_oe":    "Adj OE",
            "adj_de":    "Adj DE",
            "net_eff":   "Net Eff",
            "adj_tempo": "Tempo",
            "efg_pct":   "eFG%",
        }
        show_cols = [c for c in display_cols if c in top25.columns]
        display_df = top25[show_cols].rename(columns=display_cols)

        # Round numerics
        for col in ["Adj OE","Adj DE","Net Eff","Tempo"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(1)
        if "eFG%" in display_df.columns:
	    display_df["eFG%"] = pd.to_numeric(display_df["eFG%"], errors="coerce").round(3)

        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                "Net Eff": st.column_config.NumberColumn("Net Eff", format="%+.1f"),
                "eFG%":    st.column_config.NumberColumn("eFG%",    format="%.3f"),
            }
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Efficiency landscape scatter ──────────────────────────────────────────
    st.markdown("### 📍 Efficiency Landscape")
    st.markdown('<div class="tag">Offense vs Defense · All D1 Teams · Lower defensive efficiency = better defense</div><br>', unsafe_allow_html=True)

    if "adj_oe" in df.columns and "adj_de" in df.columns and "conference" in df.columns:
        confs  = sorted(df["conference"].dropna().unique().tolist())
        color_map = {c: CONF_COLORS[i % len(CONF_COLORS)] for i, c in enumerate(confs)}

        # Label top 25
        top25_teams = set(df.nlargest(25, "net_eff")["team"].tolist()) if "net_eff" in df.columns else set()
        df["label"] = df["team"].apply(lambda t: t if t in top25_teams else "")

        fig = px.scatter(
            df, x="adj_oe", y="adj_de",
            hover_name="team",
            color="conference",
            color_discrete_map=color_map,
            text="label",
            hover_data={c: True for c in ["record","net_eff","conference"] if c in df.columns},
            labels={"adj_oe": "Adj. Offensive Efficiency", "adj_de": "Adj. Defensive Efficiency",
                    "conference": "Conference"},
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(marker=dict(size=7, opacity=0.8),
                          textposition="top center",
                          textfont=dict(size=8, color="#94a3b8"))
        # Quadrant lines
        med_oe = df["adj_oe"].median()
        med_de = df["adj_de"].median()
        for val, axis in [(med_oe,"x"),(med_de,"y")]:
            fig.add_shape(type="line",
                x0=val if axis=="x" else df["adj_oe"].min(),
                x1=val if axis=="x" else df["adj_oe"].max(),
                y0=val if axis=="y" else df["adj_de"].min(),
                y1=val if axis=="y" else df["adj_de"].max(),
                line=dict(color="#1e2d45", width=1, dash="dot"))
        # Quadrant labels
        x_max = df["adj_oe"].max(); x_min = df["adj_oe"].min()
        y_max = df["adj_de"].max(); y_min = df["adj_de"].min()
        for text, x, y in [
            ("ELITE", x_max-1, y_min+0.5),
            ("GOOD OFFENSE", x_max-1, y_max-0.5),
            ("GOOD DEFENSE", x_min+1, y_min+0.5),
            ("REBUILDING", x_min+1, y_max-0.5),
        ]:
            fig.add_annotation(x=x, y=y, text=text, showarrow=False,
                               font=dict(size=9, color="#1e2d45"),
                               xanchor="right" if "GOOD O" in text or "ELITE" in text else "left")

        fig.update_layout(**PLOT_THEME, height=520,
                          legend=dict(font=dict(size=10), itemsizing="constant",
                                      bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Best offense vs best defense side by side ─────────────────────────────
    st.markdown("### ⚡ Best Offenses vs Best Defenses")
    off_col, def_col = st.columns(2)

    if "adj_oe" in df.columns:
        with off_col:
            st.markdown('<div class="tag orange">Top 10 Offenses</div><br>', unsafe_allow_html=True)
            top_off = df.nlargest(10, "adj_oe")[["team","adj_oe","conference"]].sort_values("adj_oe")
            fig_off = go.Figure(go.Bar(
                x=top_off["adj_oe"], y=top_off["team"],
                orientation="h",
                marker_color="#f97316",
                text=top_off["adj_oe"].round(1),
                textposition="outside",
            ))
            fig_off.update_layout(**PLOT_THEME, height=340,
                                  xaxis_title="Adj. Offensive Efficiency",
                                  margin=dict(l=0,r=40,t=10,b=10))
            st.plotly_chart(fig_off, use_container_width=True)

    if "adj_de" in df.columns:
        with def_col:
            st.markdown('<div class="tag green">Top 10 Defenses</div><br>', unsafe_allow_html=True)
            top_def = df.nsmallest(10, "adj_de")[["team","adj_de","conference"]].sort_values("adj_de", ascending=False)
            fig_def = go.Figure(go.Bar(
                x=top_def["adj_de"], y=top_def["team"],
                orientation="h",
                marker_color="#22c55e",
                text=top_def["adj_de"].round(1),
                textposition="outside",
            ))
            fig_def.update_layout(**PLOT_THEME, height=340,
                                  xaxis_title="Adj. Defensive Efficiency (lower = better)",
                                  margin=dict(l=0,r=40,t=10,b=10))
            st.plotly_chart(fig_def, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Conference strength ───────────────────────────────────────────────────
    st.markdown("### 🏛️ Conference Strength")
    st.markdown('<div class="tag">Average Net Efficiency by Conference · Min 6 teams</div><br>', unsafe_allow_html=True)

    if "conference" in df.columns and "net_eff" in df.columns:
        conf_df = (df.groupby("conference")
                     .agg(avg_net=("net_eff","mean"), teams=("team","count"))
                     .reset_index()
                     .query("teams >= 6")
                     .sort_values("avg_net", ascending=True))

        fig_conf = go.Figure(go.Bar(
            x=conf_df["avg_net"],
            y=conf_df["conference"],
            orientation="h",
            marker_color=["#f97316" if v > 0 else "#64748b" for v in conf_df["avg_net"]],
            text=conf_df["avg_net"].round(2),
            textposition="outside",
        ))
        fig_conf.update_layout(**PLOT_THEME, height=420,
                               xaxis_title="Avg. Net Efficiency",
                               margin=dict(l=0,r=60,t=10,b=10))
        st.plotly_chart(fig_conf, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Hottest teams (recent form) ───────────────────────────────────────────
    if not game_df.empty and "team" in game_df.columns:
        st.markdown("### 🔥 Hottest Teams Right Now")
        st.markdown('<div class="tag">Best record in last 10 games · Min 8 games played</div><br>', unsafe_allow_html=True)

        game_df.columns = [c.lower() for c in game_df.columns]
        game_df["date"] = pd.to_datetime(game_df["date"], errors="coerce")

        recent = (game_df.sort_values("date", ascending=False)
                         .groupby("team")
                         .head(10))
        form = (recent.groupby("team")
                      .agg(
                          wins=("result", lambda x: (x=="W").sum()),
                          games=("result", "count"),
                      )
                      .reset_index()
                      .query("games >= 8"))
        form["win_pct"] = form["wins"] / form["games"]
        form["record"]  = form["wins"].astype(str) + "-" + (form["games"]-form["wins"]).astype(str)
        form = form.sort_values("win_pct", ascending=False).head(10)

        # Merge in conference and net eff
        if "conference" in df.columns:
            form = form.merge(df[["team","conference","net_eff","adj_oe","adj_de"]],
                              on="team", how="left")

        form_display = form[["team","record","win_pct"] +
                            [c for c in ["conference","net_eff"] if c in form.columns]]
        form_display = form_display.rename(columns={
            "team":"Team","record":"Last 10","win_pct":"Win%",
            "conference":"Conf","net_eff":"Net Eff"
        })
        form_display["Win%"] = form_display["Win%"].round(3)
        if "Net Eff" in form_display.columns:
            form_display["Net Eff"] = form_display["Net Eff"].round(1)

        st.dataframe(form_display, use_container_width=True, hide_index=True,
                     column_config={
                         "Win%":    st.column_config.NumberColumn("Win%",    format="%.0%"),
                         "Net Eff": st.column_config.NumberColumn("Net Eff", format="%+.1f"),
                     })