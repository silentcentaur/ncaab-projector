import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

def logistic(x): return 1 / (1 + np.exp(-x))

def recent_form_score(games: pd.DataFrame, n: int = 10) -> float:
    if games.empty: return 0.0
    games = games.copy()
    games["date"] = pd.to_datetime(games["date"], errors="coerce")
    games = games.sort_values("date", ascending=False).head(n)
    if games.empty: return 0.0
    weights = np.array([1 / (i + 1) for i in range(len(games))])
    results = np.array([1.0 if r == "W" else -1.0 for r in games["result"].fillna("L")])
    return float(np.dot(weights, results) / weights.sum())

def avg_margin(games: pd.DataFrame, n: int = 10) -> float:
    if games.empty: return 0.0
    games = games.copy()
    games["date"]   = pd.to_datetime(games["date"], errors="coerce")
    games["margin"] = pd.to_numeric(games["margin"], errors="coerce")
    games = games.sort_values("date", ascending=False).head(n)
    return float(games["margin"].mean()) if not games["margin"].isna().all() else 0.0

def compute_win_prob(ra, rb, venue, weights, games_a, games_b):
    def g(row, col):
        v = row.get(col)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def diff(va, vb, flip=False):
        """Return va-vb (or vb-va if flip), or None if either is missing/zero."""
        if va is None or vb is None: return None
        if va == 0.0 and vb == 0.0: return None  # both zero = bad data
        return (vb - va) if flip else (va - vb)

    oe_a = g(ra,"adj_oe"); oe_b = g(rb,"adj_oe")
    de_a = g(ra,"adj_de"); de_b = g(rb,"adj_de")

    oe_diff     = (oe_a - oe_b)   if oe_a and oe_b else 0.0
    de_diff     = (de_b - de_a)   if de_a and de_b else 0.0
    efg_diff    = diff(g(ra,"efg_pct"), g(rb,"efg_pct"))
    tov_diff    = diff(g(ra,"tov_pct"), g(rb,"tov_pct"), flip=True)
    orb_diff    = diff(g(ra,"orb_pct"), g(rb,"orb_pct"))
    sos_diff    = diff(g(ra,"sos_oe"),  g(rb,"sos_oe"))
    form_diff   = recent_form_score(games_a) - recent_form_score(games_b)
    margin_diff = avg_margin(games_a)        - avg_margin(games_b)
    hca         = {"Home":3.5,"Neutral":0.0,"Away":-3.5}[venue]

    score = (
        weights["oe"]     * oe_diff                          * 0.15 +
        weights["de"]     * de_diff                          * 0.15 +
        weights["efg"]    * (efg_diff or 0.0)                * 8.0  +
        weights["tov"]    * (tov_diff or 0.0)                * 8.0  +
        weights["orb"]    * (orb_diff or 0.0)                * 5.0  +
        weights["sos"]    * (sos_diff or 0.0)                * 0.05 +
        weights["form"]   * form_diff                        * 1.5  +
        weights["margin"] * margin_diff                      * 0.08 +
        hca * 0.15
    )
    prob = logistic(score)
    return round(prob, 4), round(1 - prob, 4)

def expected_score(oe, de, opp_oe, opp_de, tempo, opp_tempo):
    t = (tempo + opp_tempo) / 2
    return round(((oe + opp_de) / 2) / 100 * t, 1), round(((opp_oe + de) / 2) / 100 * t, 1)

def stat_bar(label, va, vb, higher_is_better=True, fmt=".2f"):
    if va is None or vb is None: 
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#334155;margin-bottom:0.75rem;">{label}: no data available</div>', unsafe_allow_html=True)
        return
    if pd.isna(va) or pd.isna(vb): return
    # Treat 0.0 for both as missing data (bad ESPN box score)
    if va == 0.0 and vb == 0.0:
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#334155;margin-bottom:0.75rem;">{label}: no data available</div>', unsafe_allow_html=True)
        return
    total = abs(va) + abs(vb)
    if total == 0: return
    tp     = abs(va) / total * 100
    better = (va > vb) if higher_is_better else (va < vb)
    tc     = "#f97316" if better else "#64748b"
    oc     = "#f97316" if not better else "#64748b"
    st.markdown(f"""
    <div style="margin-bottom:0.75rem;">
        <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                    font-size:0.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">
            <span style="color:{tc};">{va:{fmt}}</span>
            <span>{label}</span>
            <span style="color:{oc};">{vb:{fmt}}</span>
        </div>
        <div style="background:#1e2d45;border-radius:4px;height:10px;overflow:hidden;display:flex;">
            <div style="width:{tp:.1f}%;background:{tc};"></div>
            <div style="flex:1;background:{oc};"></div>
        </div>
    </div>""", unsafe_allow_html=True)

DEFAULTS = {"oe":1.0,"de":1.0,"efg":0.8,"tov":0.6,"orb":0.5,"sos":0.4,"form":0.6,"margin":0.4}

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# ⚔️ Matchup Simulator")

    df      = db.get_team_data()
    teams   = db.team_list()
    game_df = db.get_game_history()

    if df.empty or not teams:
        st.warning("No data in database yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]

    # Build name map from live data
    if not game_df.empty:
        game_df.columns = [c.lower() for c in game_df.columns]
        nm.build(df["team"].dropna().tolist(),
                 game_df["team"].dropna().unique().tolist())

    # ── Team pickers ──────────────────────────────────────────────────────────
    c1, cv, c2 = st.columns([5,1,5])
    with c1: team_a = st.selectbox("Team A", teams, index=None, placeholder="Type to search...")
    with cv: st.markdown("<div style='text-align:center;font-size:1.8rem;color:#64748b;padding-top:1.8rem;'>VS</div>", unsafe_allow_html=True)
    with c2: team_b = st.selectbox("Team B", teams, index=None, placeholder="Type to search...")
    venue = st.select_slider("Venue (from Team A's perspective)",
                             options=["Away","Neutral","Home"], value="Neutral")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Model weights ─────────────────────────────────────────────────────────
    with st.expander("⚙️  Customize Prediction Model", expanded=False):
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;">0 = ignore · 1 = default · 2 = double weight</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Efficiency**")
            w_oe     = st.slider("Adj. Offensive Efficiency", 0.0, 2.0, DEFAULTS["oe"],     0.1, key="w_oe")
            w_de     = st.slider("Adj. Defensive Efficiency", 0.0, 2.0, DEFAULTS["de"],     0.1, key="w_de")
            w_sos    = st.slider("Strength of Schedule",      0.0, 2.0, DEFAULTS["sos"],    0.1, key="w_sos")
            w_margin = st.slider("Recent Point Margin",       0.0, 2.0, DEFAULTS["margin"], 0.1, key="w_margin")
        with col2:
            st.markdown("**Four Factors**")
            w_efg  = st.slider("Effective FG%",    0.0, 2.0, DEFAULTS["efg"],  0.1, key="w_efg")
            w_tov  = st.slider("Turnover Rate",    0.0, 2.0, DEFAULTS["tov"],  0.1, key="w_tov")
            w_orb  = st.slider("Off. Rebound Rate",0.0, 2.0, DEFAULTS["orb"],  0.1, key="w_orb")
            w_form = st.slider("Recent Form (W/L)",0.0, 2.0, DEFAULTS["form"], 0.1, key="w_form")
        if st.button("Reset to Defaults"):
            for k, v in DEFAULTS.items():
                st.session_state[f"w_{k}"] = v
            st.rerun()

        active = {k:v for k,v in {"Off.Eff":w_oe,"Def.Eff":w_de,"eFG%":w_efg,
                                   "TOV%":w_tov,"ORB%":w_orb,"SOS":w_sos,
                                   "Form":w_form,"Margin":w_margin}.items() if v>0}
        total_w = sum(active.values()) or 1
        colors  = ["#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa","#f43f5e","#84cc16","#fb923c"]
        bar_html = '<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;width:100%;margin-top:1rem;">'
        for i,(lbl,w) in enumerate(active.items()):
            bar_html += f'<div style="width:{w/total_w*100:.1f}%;background:{colors[i%len(colors)]};"></div>'
        bar_html += '</div><div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:6px;">'
        for i,(lbl,w) in enumerate(active.items()):
            bar_html += f'<span style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:{colors[i%len(colors)]};">{lbl} {w:.1f}</span>'
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

    weights = {"oe":w_oe,"de":w_de,"efg":w_efg,"tov":w_tov,
               "orb":w_orb,"sos":w_sos,"form":w_form,"margin":w_margin}

    if not team_a or not team_b:
        st.markdown("""
        <div style="margin-top:2rem;text-align:center;padding:3rem;border:1px dashed #1e2d45;border-radius:8px;">
            <div style="font-size:2rem;color:#334155;font-weight:700;">SELECT TWO TEAMS TO BEGIN</div>
            <div style="font-size:0.8rem;color:#334155;margin-top:0.5rem;">Type a team name in either box above</div>
        </div>""", unsafe_allow_html=True)
        return
    if team_a == team_b:
        st.warning("Select two different teams.")
        return

    ra = df[df["team"] == team_a].iloc[0]
    rb = df[df["team"] == team_b].iloc[0]

    # Get game history using name map
    games_a = nm.get_team_games(game_df, df, team_a)
    games_b = nm.get_team_games(game_df, df, team_b)

    pa, pb = compute_win_prob(ra, rb, venue, weights, games_a, games_b)

    # ── Win probability banner ────────────────────────────────────────────────
    st.markdown(f"""
    <div class="matchup-banner">
        <div style="display:flex;justify-content:space-around;align-items:center;">
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;">{team_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#f97316;">{pa*100:.1f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;">WIN PROBABILITY</div>
            </div>
            <div style="font-size:1.2rem;color:#334155;">VS</div>
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;">{team_b}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#64748b;">{pb*100:.1f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;">WIN PROBABILITY</div>
            </div>
        </div>
        <div style="margin-top:1.5rem;">
            <div style="background:#1e2d45;border-radius:6px;height:20px;overflow:hidden;display:flex;">
                <div style="width:{pa*100:.1f}%;background:#f97316;"></div>
                <div style="flex:1;background:#334155;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                        font-size:0.65rem;color:#64748b;margin-top:4px;">
                <span>{team_a}</span><span>{venue}</span><span>{team_b}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Projected score ───────────────────────────────────────────────────────
    oe_a=float(ra.get("adj_oe") or 100); de_a=float(ra.get("adj_de") or 100)
    oe_b=float(rb.get("adj_oe") or 100); de_b=float(rb.get("adj_de") or 100)
    t_a =float(ra.get("adj_tempo") or 68); t_b=float(rb.get("adj_tempo") or 68)
    s_a, s_b = expected_score(oe_a, de_a, oe_b, de_b, t_a, t_b)
    sc1,sc2,sc3 = st.columns([3,1,3])
    sc1.metric(f"{team_a} Proj. Score", s_a)
    sc2.markdown("<div style='text-align:center;padding-top:1.5rem;color:#64748b;'>–</div>", unsafe_allow_html=True)
    sc3.metric(f"{team_b} Proj. Score", s_b)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Dual radar chart ──────────────────────────────────────────────────────
    import plotly.graph_objects as go

    def get_percentile(val, all_vals, higher_is_better=True):
        if val is None or pd.isna(val): return None
        arr = [v for v in all_vals if v is not None and not pd.isna(v)]
        if not arr: return None
        pct = sum(v <= val for v in arr) / len(arr) * 100
        return pct if higher_is_better else 100 - pct

    df2 = db.get_team_data()
    if not df2.empty:
        df2.columns = [c.lower() for c in df2.columns]
        def col_vals(col):
            return pd.to_numeric(df2[col], errors="coerce").dropna().tolist() if col in df2.columns else []

        radar_metrics = [
            ("Off. Eff.",  "adj_oe",      True),
            ("Def. Eff.",  "adj_de",      False),
            ("Tempo",      "adj_tempo",   True),
            ("eFG%",       "efg_pct",     True),
            ("TOV%",       "tov_pct",     False),
            ("ORB%",       "orb_pct",     True),
            ("FTR",        "ftr",         True),
            ("Opp eFG%",   "opp_efg_pct", False),
        ]
        labels = [m[0] for m in radar_metrics]

        def team_percentiles(row):
            vals = []
            for label, col, hib in radar_metrics:
                v = row.get(col)
                v = float(v) if v is not None and not pd.isna(v) else None
                pct = get_percentile(v, col_vals(col), hib)
                vals.append(pct if pct is not None else 0)
            return vals

        pcts_a = team_percentiles(ra)
        pcts_b = team_percentiles(rb)
        labels_closed = labels + [labels[0]]
        pcts_a_closed = pcts_a + [pcts_a[0]]
        pcts_b_closed = pcts_b + [pcts_b[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=pcts_a_closed, theta=labels_closed,
            fill="toself", name=team_a,
            line=dict(color="#f97316", width=2),
            fillcolor="rgba(249,115,22,0.15)"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=pcts_b_closed, theta=labels_closed,
            fill="toself", name=team_b,
            line=dict(color="#06b6d4", width=2),
            fillcolor="rgba(6,182,212,0.15)"
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0,100],
                                tickfont=dict(size=8, color="#475569"),
                                gridcolor="#1e2d45",
                                tickvals=[25,50,75,100],
                                ticktext=["25%","50%","75%","100%"]),
                angularaxis=dict(tickfont=dict(size=11, color="#94a3b8"), gridcolor="#1e2d45"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f1f5f9", family="DM Sans"),
            legend=dict(font=dict(size=11, color="#94a3b8"),
                        bgcolor="rgba(0,0,0,0)", x=0.5, y=-0.1,
                        orientation="h", xanchor="center"),
            margin=dict(l=60, r=60, t=40, b=60),
            title=dict(text="SEASON PROFILE VS. NATIONAL PERCENTILES",
                       font=dict(family="Bebas Neue", size=16, color="#f1f5f9"),
                       x=0, xanchor="left"),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Factor breakdown ──────────────────────────────────────────────────────
    st.markdown("### Factor Breakdown")
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;margin-bottom:1rem;">How each active factor favors each team</div>', unsafe_allow_html=True)

    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    form_a   = recent_form_score(games_a)
    form_b   = recent_form_score(games_b)
    margin_a = avg_margin(games_a)
    margin_b = avg_margin(games_b)

    factors = [
        ("Adj. Offensive Eff.", g(ra,"adj_oe",100), g(rb,"adj_oe",100), True,  ".1f", w_oe),
        ("Adj. Defensive Eff.", g(ra,"adj_de",100), g(rb,"adj_de",100), False, ".1f", w_de),
        ("Effective FG%",       g(ra,"efg_pct"),     g(rb,"efg_pct"),    True,  ".3f", w_efg),
        ("Turnover Rate",       g(ra,"tov_pct"),     g(rb,"tov_pct"),    False, ".3f", w_tov),
        ("Off. Rebound Rate",   g(ra,"orb_pct"),     g(rb,"orb_pct"),    True,  ".3f", w_orb),
        ("Strength of Schedule",g(ra,"sos_oe"),      g(rb,"sos_oe"),     True,  ".3f", w_sos),
        ("Recent Form",         form_a,              form_b,             True,  ".2f", w_form),
        ("Recent Avg Margin",   margin_a,            margin_b,           True,  ".1f", w_margin),
    ]
    for label, va, vb, hib, fmt, w in factors:
        if w > 0:
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:#334155;text-transform:uppercase;margin-top:0.5rem;">weight: {w:.1f}</div>', unsafe_allow_html=True)
            stat_bar(label, va, vb, hib, fmt)

    # ── Recent form ───────────────────────────────────────────────────────────
    st.markdown("### Recent Form (Last 10 Games)")
    fc1, fc2 = st.columns(2)
    for col_w, tname, tgames in [(fc1, team_a, games_a), (fc2, team_b, games_b)]:
        if not tgames.empty and "result" in tgames.columns:
            tg = tgames.copy()
            tg["date"] = pd.to_datetime(tg["date"], errors="coerce")
            tg = tg.sort_values("date", ascending=False).head(10)
            w  = (tg["result"] == "W").sum()
            l  = (tg["result"] == "L").sum()
            col_w.markdown(f"**{tname}**: {w}W – {l}L")
            col_w.markdown("".join([
                f'<span class="tag {"green" if r=="W" else "red"}" style="margin:2px;">{r}</span>'
                for r in tg["result"].tolist()
            ]), unsafe_allow_html=True)
        else:
            col_w.markdown(f"**{tname}**: No game data")