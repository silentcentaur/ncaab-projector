import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

REGIONS = ["East", "West", "South", "Midwest"]
SEEDS   = list(range(1, 17))
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]

DARK_CSS = """
<style>
[data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
.region-header {
    font-family: 'Bebas Neue', sans-serif; font-size: 1.3rem;
    color: #f97316; letter-spacing: 0.1em; margin-bottom: 0.5rem;
}
.round-label {
    font-family: 'DM Mono', monospace; font-size: 0.6rem;
    color: #475569; text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 6px; padding: 2px 6px;
    border-left: 2px solid #f97316; display: inline-block;
}
.team-tbd {
    font-family: 'DM Mono', monospace; font-size: 0.7rem;
    color: #2d4a6b; padding: 5px 10px; border: 1px dashed #1e3a5f;
    border-radius: 5px; margin: 2px 0; background: #0a1628;
}
/* Selectbox contrast */
div[data-baseweb="select"] > div {
    background-color: #112240 !important;
    border-color: #2d4a6b !important;
    color: #e2e8f0 !important;
}
div[data-baseweb="select"] > div:hover { border-color: #f97316 !important; }
div[data-baseweb="select"] svg { color: #64748b !important; }
div[data-baseweb="popover"] { background-color: #112240 !important; }
</style>
"""

def init_bracket():
    if "bracket_teams" not in st.session_state:
        st.session_state.bracket_teams = {r: {s: None for s in SEEDS} for r in REGIONS}
    if "bracket_picks" not in st.session_state:
        st.session_state.bracket_picks = {r: {} for r in REGIONS}
    if "final_four" not in st.session_state:
        st.session_state.final_four = {}
    if "expanded_matchup" not in st.session_state:
        st.session_state.expanded_matchup = None

def get_winner(region, round_idx, game_idx):
    return st.session_state.bracket_picks.get(region, {}).get(round_idx, {}).get(game_idx)

def set_winner(region, round_idx, game_idx, team):
    bp = st.session_state.bracket_picks
    if region not in bp: bp[region] = {}
    if round_idx not in bp[region]: bp[region][round_idx] = {}
    bp[region][round_idx][game_idx] = team
    clear_downstream(region, round_idx, game_idx)

def clear_downstream(region, round_idx, game_idx):
    next_round = round_idx + 1
    next_game  = game_idx // 2
    picks = st.session_state.bracket_picks.get(region, {})
    if next_round in picks and next_game in picks[next_round]:
        del picks[next_round][next_game]
        clear_downstream(region, next_round, next_game)

def get_team_in_slot(region, round_idx, game_idx, slot):
    if round_idx == 0:
        seed = FIRST_ROUND_PAIRS[game_idx][slot]
        return st.session_state.bracket_teams[region].get(seed)
    return get_winner(region, round_idx - 1, game_idx * 2 + slot)

def all_selected_teams():
    selected = set()
    for r in REGIONS:
        for s in SEEDS:
            t = st.session_state.bracket_teams[r].get(s)
            if t:
                selected.add(t)
    return selected

def render_team_slot(region, round_idx, game_idx, slot, teams, col):
    team   = get_team_in_slot(region, round_idx, game_idx, slot)
    winner = get_winner(region, round_idx, game_idx)
    other  = get_team_in_slot(region, round_idx, game_idx, 1 - slot)
    seed   = FIRST_ROUND_PAIRS[game_idx][slot] if round_idx == 0 else None

    if round_idx == 0:
        used      = all_selected_teams() - ({team} if team else set())
        available = [""] + [t for t in teams if t not in used]
        cur_idx   = available.index(team) if team in available else 0

        with col:
            seed_label = f"#{seed}" if seed else ""
            c_sel, c_clr = st.columns([5, 1])
            with c_sel:
                new_val = st.selectbox(
                    seed_label,
                    available,
                    index=cur_idx,
                    key=f"sel_{region}_{game_idx}_{slot}",
                    placeholder="Search...",
                )
            with c_clr:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if team and st.button("✕", key=f"clr_{region}_{game_idx}_{slot}", help="Clear"):
                    st.session_state.bracket_teams[region][seed] = None
                    clear_downstream(region, 0, game_idx)
                    st.rerun()

            if new_val != (team or ""):
                st.session_state.bracket_teams[region][seed] = new_val if new_val else None
                clear_downstream(region, 0, game_idx)
                st.rerun()
    else:
        with col:
            if not team:
                st.markdown('<div class="team-tbd">TBD</div>', unsafe_allow_html=True)
                return
            prefix = "✓ " if winner == team else ""
            disabled = not other
            if st.button(
                f"{prefix}{team[:24]}",
                key=f"pick_{region}_{round_idx}_{game_idx}_{slot}",
                help=f"Pick {team}",
                disabled=disabled,
            ):
                set_winner(region, round_idx, game_idx, team)
                st.rerun()

def render_compare_button(region, round_idx, game_idx, col):
    team_a = get_team_in_slot(region, round_idx, game_idx, 0)
    team_b = get_team_in_slot(region, round_idx, game_idx, 1)
    if not team_a or not team_b:
        return
    key    = (region, round_idx, game_idx)
    is_exp = st.session_state.expanded_matchup == key
    if col.button("▲" if is_exp else "▼", key=f"cmp_{region}_{round_idx}_{game_idx}", help="Compare"):
        st.session_state.expanded_matchup = None if is_exp else key
        st.rerun()

def render_matchup(region, round_idx, game_idx, df_stats, teams):
    c_a, c_vs, c_b, c_cmp = st.columns([5, 0.5, 5, 1])
    render_team_slot(region, round_idx, game_idx, 0, teams, c_a)
    c_vs.markdown("<div style='text-align:center;color:#2d4a6b;padding-top:28px;font-size:0.75rem;font-weight:bold;'>vs</div>", unsafe_allow_html=True)
    render_team_slot(region, round_idx, game_idx, 1, teams, c_b)
    with c_cmp:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        render_compare_button(region, round_idx, game_idx, c_cmp)

def render_comparison_panel(team_a, team_b, region, round_idx, game_idx, df_stats):
    if df_stats.empty:
        return
    ra_rows = df_stats[df_stats["team"] == team_a]
    rb_rows = df_stats[df_stats["team"] == team_b]
    if ra_rows.empty or rb_rows.empty:
        st.info("Stats not available for one or both teams.")
        return

    ra = ra_rows.iloc[0]
    rb = rb_rows.iloc[0]

    import plotly.graph_objects as go

    def get_pct(val, col, hib=True):
        if val is None or pd.isna(val): return 0
        arr = pd.to_numeric(df_stats[col], errors="coerce").dropna().tolist()
        if not arr: return 0
        p = sum(v <= val for v in arr) / len(arr) * 100
        return p if hib else 100 - p

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

    def row_pcts(row):
        vals = []
        for _, col, hib in radar_metrics:
            v = row.get(col)
            v = float(v) if v is not None and not pd.isna(v) else None
            vals.append(get_pct(v, col, hib) if v is not None else 0)
        return vals

    labels = [m[0] for m in radar_metrics]
    pcts_a = row_pcts(ra)
    pcts_b = row_pcts(rb)
    lc = labels + [labels[0]]
    pac = pcts_a + [pcts_a[0]]
    pbc = pcts_b + [pcts_b[0]]

    st.markdown("---")
    st.markdown(f"### ⚔️ {team_a} vs {team_b}")
    rc1, rc2 = st.columns(2)

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=pac, theta=lc, fill="toself", name=team_a,
                                   line=dict(color="#f97316", width=2),
                                   fillcolor="rgba(249,115,22,0.15)"))
    fig.add_trace(go.Scatterpolar(r=pbc, theta=lc, fill="toself", name=team_b,
                                   line=dict(color="#06b6d4", width=2),
                                   fillcolor="rgba(6,182,212,0.15)"))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(visible=True, range=[0,100],
                                   tickfont=dict(size=8, color="#475569"),
                                   gridcolor="#1e2d45",
                                   tickvals=[25,50,75,100],
                                   ticktext=["25%","50%","75%","100%"]),
                   angularaxis=dict(tickfont=dict(size=10, color="#94a3b8"), gridcolor="#1e2d45")),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f1f5f9", family="DM Sans"),
        legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)",
                    x=0.5, y=-0.15, orientation="h", xanchor="center"),
        margin=dict(l=50, r=50, t=30, b=50), height=300,
    )
    rc1.plotly_chart(fig, use_container_width=True)

    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    with rc2:
        for label, va, vb, hib, fmt in [
            ("Adj OE", g(ra,"adj_oe",100),   g(rb,"adj_oe",100),   True,  ".1f"),
            ("Adj DE", g(ra,"adj_de",100),   g(rb,"adj_de",100),   False, ".1f"),
            ("eFG%",   g(ra,"efg_pct"),      g(rb,"efg_pct"),      True,  ".3f"),
            ("TOV%",   g(ra,"tov_pct"),      g(rb,"tov_pct"),      False, ".3f"),
            ("ORB%",   g(ra,"orb_pct"),      g(rb,"orb_pct"),      True,  ".3f"),
            ("Tempo",  g(ra,"adj_tempo",68), g(rb,"adj_tempo",68), True,  ".1f"),
        ]:
            total = abs(va) + abs(vb)
            if total == 0: continue
            tp    = abs(va) / total * 100
            better = (va > vb) if hib else (va < vb)
            tc = "#f97316" if better else "#64748b"
            oc = "#06b6d4" if not better else "#64748b"
            st.markdown(f"""
            <div style="margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                            font-size:0.65rem;color:#94a3b8;margin-bottom:3px;">
                    <span style="color:{tc};">{va:{fmt}}</span>
                    <span>{label}</span>
                    <span style="color:{oc};">{vb:{fmt}}</span>
                </div>
                <div style="background:#1e2d45;border-radius:3px;height:8px;overflow:hidden;display:flex;">
                    <div style="width:{tp:.1f}%;background:{tc};"></div>
                    <div style="flex:1;background:{oc};"></div>
                </div>
            </div>""", unsafe_allow_html=True)

    pb1, pb2 = st.columns(2)
    if pb1.button(f"🏆 Pick {team_a}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_0",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_a)
        st.rerun()
    if pb2.button(f"🏆 Pick {team_b}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_1",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_b)
        st.rerun()

def render_region(region, df_stats, teams):
    st.markdown(f'<div class="region-header">{region} Region</div>', unsafe_allow_html=True)
    round_names = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]

    for round_idx in range(4):
        num_games = 8 // (2 ** round_idx)
        st.markdown(f'<div class="round-label">{round_names[round_idx]}</div>', unsafe_allow_html=True)
        for game_idx in range(num_games):
            render_matchup(region, round_idx, game_idx, df_stats, teams)
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    return get_winner(region, 3, 0)

def render_final_four(df_stats):
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.8rem;color:#f97316;letter-spacing:0.1em;text-align:center;">🏆 FINAL FOUR & CHAMPIONSHIP</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    sf_matchups = [("East","West","sf1"), ("South","Midwest","sf2")]
    sf_winners  = {}

    for r1, r2, slot in sf_matchups:
        t1 = get_winner(r1, 3, 0)
        t2 = get_winner(r2, 3, 0)
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65rem;color:#475569;text-transform:uppercase;margin-bottom:4px;">{r1} vs {r2}</div>', unsafe_allow_html=True)
        c_a, c_vs, c_b, c_cmp = st.columns([5, 0.5, 5, 1])

        for col, team, s in [(c_a, t1, 0), (c_b, t2, 1)]:
            with col:
                if not team:
                    st.markdown('<div class="team-tbd">TBD</div>', unsafe_allow_html=True)
                else:
                    winner = st.session_state.final_four.get(slot)
                    prefix = "✓ " if winner == team else ""
                    if st.button(f"{prefix}{team[:24]}", key=f"ff_{slot}_{s}",
                                 disabled=(not t1 or not t2)):
                        st.session_state.final_four[slot] = team
                        if "champion" in st.session_state.final_four:
                            del st.session_state.final_four["champion"]
                        st.rerun()

        c_vs.markdown("<div style='text-align:center;color:#2d4a6b;padding-top:6px;font-size:0.75rem;font-weight:bold;'>vs</div>", unsafe_allow_html=True)

        ff_key = ("ff", slot)
        is_exp = st.session_state.expanded_matchup == ff_key
        if t1 and t2:
            if c_cmp.button("▲" if is_exp else "▼", key=f"cmp_ff_{slot}", help="Compare"):
                st.session_state.expanded_matchup = None if is_exp else ff_key
                st.rerun()
        if is_exp and t1 and t2:
            render_comparison_panel(t1, t2, "ff", slot, 0, df_stats)

        sf_winners[slot] = st.session_state.final_four.get(slot)
        st.markdown("<br>", unsafe_allow_html=True)

    ct1 = sf_winners.get("sf1")
    ct2 = sf_winners.get("sf2")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;color:#fbbf24;letter-spacing:0.1em;">🏆 Championship</div>', unsafe_allow_html=True)
    c_a, c_vs, c_b, c_cmp = st.columns([5, 0.5, 5, 1])
    for col, team, s in [(c_a, ct1, 0), (c_b, ct2, 1)]:
        with col:
            if not team:
                st.markdown('<div class="team-tbd">TBD</div>', unsafe_allow_html=True)
            else:
                champ  = st.session_state.final_four.get("champion")
                prefix = "🏆 " if champ == team else ""
                if st.button(f"{prefix}{team[:24]}", key=f"champ_{s}",
                             disabled=(not ct1 or not ct2)):
                    st.session_state.final_four["champion"] = team
                    st.rerun()
    c_vs.markdown("<div style='text-align:center;color:#2d4a6b;padding-top:6px;font-size:0.75rem;font-weight:bold;'>vs</div>", unsafe_allow_html=True)
    ff_key = ("ff", "champ")
    is_exp = st.session_state.expanded_matchup == ff_key
    if ct1 and ct2:
        if c_cmp.button("▲" if is_exp else "▼", key="cmp_ff_champ", help="Compare"):
            st.session_state.expanded_matchup = None if is_exp else ff_key
            st.rerun()
        if is_exp:
            render_comparison_panel(ct1, ct2, "ff", "champ", 0, df_stats)

    champ = st.session_state.final_four.get("champion")
    if champ:
        st.markdown(f"""
        <div style="text-align:center;margin-top:2rem;padding:2rem;
                    background:linear-gradient(135deg,#1a2c1a,#0f172a);
                    border:2px solid #fbbf24;border-radius:12px;">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;color:#fbbf24;letter-spacing:0.2em;">YOUR CHAMPION</div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:2.5rem;color:#fbbf24;">{champ}</div>
            <div style="font-size:2rem;">🏆</div>
        </div>""", unsafe_allow_html=True)

def show():
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    st.markdown("# 🏆 Bracket Simulator")

    init_bracket()

    df_stats = db.get_team_data()
    game_df  = db.get_game_history()
    if not df_stats.empty:
        df_stats.columns = [c.lower() for c in df_stats.columns]
        if not game_df.empty:
            game_df.columns = [c.lower() for c in game_df.columns]
            nm.build(df_stats["team"].dropna().tolist(),
                     game_df["team"].dropna().unique().tolist())

    teams = db.team_list()

    # ── Duplicate warning ─────────────────────────────────────────────────────
    selected = [
        st.session_state.bracket_teams[r][s]
        for r in REGIONS for s in SEEDS
        if st.session_state.bracket_teams[r].get(s)
    ]
    dupes = {t for t in selected if selected.count(t) > 1}
    if dupes:
        st.error(f"⚠️ Duplicate teams: {', '.join(sorted(dupes))}. Each team can only appear once.")

    # ── Bracket tabs ──────────────────────────────────────────────────────────
    tabs = st.tabs(REGIONS + ["🏆 Final Four"])

    for i, region in enumerate(REGIONS):
        with tabs[i]:
            render_region(region, df_stats, teams)
            exp = st.session_state.expanded_matchup
            if exp and isinstance(exp, tuple) and len(exp) == 3 and exp[0] == region:
                _, r_idx, g_idx = exp
                t_a = get_team_in_slot(region, r_idx, g_idx, 0)
                t_b = get_team_in_slot(region, r_idx, g_idx, 1)
                if t_a and t_b:
                    render_comparison_panel(t_a, t_b, region, r_idx, g_idx, df_stats)

    with tabs[4]:
        render_final_four(df_stats)