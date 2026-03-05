import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

# ── Constants ────────────────────────────────────────────────────────────────
REGIONS = ["East", "West", "South", "Midwest"]
SEEDS   = list(range(1, 17))

# First round matchups by seed
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]

DARK_CSS = """
<style>
[data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
.bracket-team {
    display: flex; align-items: center; justify-content: space-between;
    padding: 4px 8px; margin: 1px 0; border-radius: 4px; cursor: pointer;
    font-family: 'DM Mono', monospace; font-size: 0.7rem;
    background: #0f172a; border: 1px solid #1e2d45;
    transition: all 0.15s; min-width: 160px; min-height: 28px;
}
.bracket-team:hover { border-color: #f97316; background: #1a2744; }
.bracket-team.winner { background: #1a2c1a; border-color: #22c55e; color: #22c55e; }
.bracket-team.loser  { opacity: 0.4; }
.bracket-team.tbd    { color: #334155; border-color: #1e2d45; cursor: default; }
.seed-badge {
    font-size: 0.6rem; color: #475569; background: #1e2d45;
    padding: 1px 4px; border-radius: 3px; margin-right: 6px; min-width: 16px; text-align: center;
}
.region-header {
    font-family: 'Bebas Neue', sans-serif; font-size: 1.3rem;
    color: #f97316; letter-spacing: 0.1em; margin-bottom: 0.5rem;
}
.round-label {
    font-family: 'DM Mono', monospace; font-size: 0.6rem;
    color: #475569; text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 4px; text-align: center;
}
.matchup-connector {
    border-left: 1px solid #1e2d45; margin: 0 4px;
}
.compare-btn {
    font-size: 0.55rem; color: #475569; background: none;
    border: none; cursor: pointer; padding: 0 2px;
}
</style>
"""

def init_bracket():
    """Initialize bracket state if not present."""
    if "bracket_teams" not in st.session_state:
        # {region: {seed: team_name}}
        st.session_state.bracket_teams = {r: {s: None for s in SEEDS} for r in REGIONS}
    if "bracket_picks" not in st.session_state:
        # {region: {round_idx: {game_idx: winner_name}}}
        st.session_state.bracket_picks = {r: {} for r in REGIONS}
    if "final_four" not in st.session_state:
        # {slot: winner} slots: "East/West", "South/Midwest", "Champion"
        st.session_state.final_four = {}
    if "expanded_matchup" not in st.session_state:
        st.session_state.expanded_matchup = None  # (region, round_idx, game_idx) or ("ff", slot)

def get_winner(region, round_idx, game_idx):
    picks = st.session_state.bracket_picks.get(region, {})
    return picks.get(round_idx, {}).get(game_idx)

def set_winner(region, round_idx, game_idx, team):
    if region not in st.session_state.bracket_picks:
        st.session_state.bracket_picks[region] = {}
    if round_idx not in st.session_state.bracket_picks[region]:
        st.session_state.bracket_picks[region][round_idx] = {}
    st.session_state.bracket_picks[region][round_idx][game_idx] = team
    # Clear downstream picks
    clear_downstream(region, round_idx, game_idx)

def clear_downstream(region, round_idx, game_idx):
    """When a pick changes, clear all picks that depended on it."""
    next_round = round_idx + 1
    next_game  = game_idx // 2
    picks = st.session_state.bracket_picks.get(region, {})
    if next_round in picks and next_game in picks[next_round]:
        old_winner = picks[next_round][next_game]
        del picks[next_round][next_game]
        clear_downstream(region, next_round, next_game)

def get_team_in_slot(region, round_idx, game_idx, slot):
    """Get team name for a slot (0 or 1) in a given round/game."""
    if round_idx == 0:
        pair = FIRST_ROUND_PAIRS[game_idx]
        seed = pair[slot]
        return st.session_state.bracket_teams[region].get(seed)
    else:
        prev_game = game_idx * 2 + slot
        return get_winner(region, round_idx - 1, prev_game)

def render_team_button(region, round_idx, game_idx, slot, df_stats, col):
    team = get_team_in_slot(region, round_idx, game_idx, slot)
    winner = get_winner(region, round_idx, game_idx)
    other_slot = 1 - slot
    other_team = get_team_in_slot(region, round_idx, game_idx, other_slot)

    if not team:
        col.markdown('<div class="bracket-team tbd">TBD</div>', unsafe_allow_html=True)
        return

    seed = ""
    if round_idx == 0:
        seed = str(FIRST_ROUND_PAIRS[game_idx][slot])

    css_class = ""
    if winner == team:
        css_class = "winner"
    elif winner and winner != team:
        css_class = "loser"

    label = f'<span class="seed-badge">{seed}</span>{team[:20]}' if seed else team[:22]

    btn_key = f"pick_{region}_{round_idx}_{game_idx}_{slot}"
    if col.button(f"{'✓ ' if winner==team else ''}{team[:18]}", key=btn_key,
                  help=f"Pick {team} as winner",
                  disabled=(not other_team)):
        set_winner(region, round_idx, game_idx, team)
        # Also close expanded matchup if it was this one and team changed
        st.rerun()

def render_compare_button(region, round_idx, game_idx, col):
    team_a = get_team_in_slot(region, round_idx, game_idx, 0)
    team_b = get_team_in_slot(region, round_idx, game_idx, 1)
    if not team_a or not team_b:
        return
    key = (region, round_idx, game_idx)
    is_expanded = st.session_state.expanded_matchup == key
    btn_label = "▼ Compare" if not is_expanded else "▲ Close"
    if col.button(btn_label, key=f"cmp_{region}_{round_idx}_{game_idx}"):
        st.session_state.expanded_matchup = None if is_expanded else key
        st.rerun()

def render_matchup(region, round_idx, game_idx, df_stats, teams_col):
    team_a = get_team_in_slot(region, round_idx, game_idx, 0)
    team_b = get_team_in_slot(region, round_idx, game_idx, 1)

    with teams_col:
        c_a, c_vs, c_b, c_cmp = st.columns([4, 0.6, 4, 1.8])
        render_team_button(region, round_idx, game_idx, 0, df_stats, c_a)
        c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:4px;font-size:0.7rem;'>vs</div>", unsafe_allow_html=True)
        render_team_button(region, round_idx, game_idx, 1, df_stats, c_b)
        render_compare_button(region, round_idx, game_idx, c_cmp)

def render_comparison_panel(team_a, team_b, region, round_idx, game_idx, df_stats):
    """Render the expanded comparison panel below the bracket."""
    if df_stats.empty:
        return

    ra_rows = df_stats[df_stats["team"] == team_a]
    rb_rows = df_stats[df_stats["team"] == team_b]
    if ra_rows.empty or rb_rows.empty:
        st.info(f"No stats available for comparison.")
        return

    ra = ra_rows.iloc[0]
    rb = rb_rows.iloc[0]

    import plotly.graph_objects as go

    def get_pct(val, col, higher_is_better=True):
        if val is None or pd.isna(val): return 0
        arr = pd.to_numeric(df_stats[col], errors="coerce").dropna().tolist()
        if not arr: return 0
        p = sum(v <= val for v in arr) / len(arr) * 100
        return p if higher_is_better else 100 - p

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

    labels    = [m[0] for m in radar_metrics]
    pcts_a    = row_pcts(ra)
    pcts_b    = row_pcts(rb)
    lc        = labels + [labels[0]]
    pac       = pcts_a + [pcts_a[0]]
    pbc       = pcts_b + [pcts_b[0]]

    st.markdown("---")
    st.markdown(f"### ⚔️ {team_a} vs {team_b}")

    rc1, rc2 = st.columns(2)

    # Radar
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
        margin=dict(l=50, r=50, t=30, b=50), height=320,
    )
    rc1.plotly_chart(fig, use_container_width=True)

    # Stat bars
    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    with rc2:
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65rem;color:#f97316;">{team_a}</div>', unsafe_allow_html=True)
        stats = [
            ("Adj OE", g(ra,"adj_oe",100), g(rb,"adj_oe",100), True,  ".1f"),
            ("Adj DE", g(ra,"adj_de",100), g(rb,"adj_de",100), False, ".1f"),
            ("eFG%",   g(ra,"efg_pct"),    g(rb,"efg_pct"),    True,  ".3f"),
            ("TOV%",   g(ra,"tov_pct"),    g(rb,"tov_pct"),    False, ".3f"),
            ("ORB%",   g(ra,"orb_pct"),    g(rb,"orb_pct"),    True,  ".3f"),
            ("Tempo",  g(ra,"adj_tempo",68),g(rb,"adj_tempo",68),True, ".1f"),
        ]
        for label, va, vb, hib, fmt in stats:
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

    # Pick buttons
    pb1, pb2 = st.columns(2)
    if pb1.button(f"🏆 Pick {team_a}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_0",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_a)
        # Keep comparison open
        st.rerun()
    if pb2.button(f"🏆 Pick {team_b}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_1",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_b)
        st.rerun()

def render_region(region, df_stats):
    st.markdown(f'<div class="region-header">{region} Region</div>', unsafe_allow_html=True)

    num_rounds = 4  # R64, R32, S16, E8
    round_names = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]

    for round_idx in range(num_rounds):
        num_games = 8 // (2 ** round_idx)
        st.markdown(f'<div class="round-label">{round_names[round_idx]}</div>', unsafe_allow_html=True)
        for game_idx in range(num_games):
            render_matchup(region, round_idx, game_idx, df_stats, st.container())
        st.markdown("<br>", unsafe_allow_html=True)

    # Return Elite 8 winner
    return get_winner(region, 3, 0)

def render_final_four(df_stats):
    st.markdown("---")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.8rem;color:#f97316;letter-spacing:0.1em;text-align:center;">🏆 FINAL FOUR & CHAMPIONSHIP</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Semifinal 1: East vs West
    # Semifinal 2: South vs Midwest
    sf_matchups = [
        ("East", "West",    "sf1"),
        ("South","Midwest", "sf2"),
    ]

    sf_winners = {}
    for r1, r2, slot in sf_matchups:
        t1 = get_winner(r1, 3, 0)
        t2 = get_winner(r2, 3, 0)
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65rem;color:#475569;text-transform:uppercase;margin-bottom:4px;">{r1} vs {r2}</div>', unsafe_allow_html=True)
        c_a, c_vs, c_b, c_cmp = st.columns([4, 0.6, 4, 1.8])

        for col, team, s in [(c_a, t1, 0), (c_b, t2, 1)]:
            if not team:
                col.markdown('<div class="bracket-team tbd">TBD</div>', unsafe_allow_html=True)
            else:
                winner = st.session_state.final_four.get(slot)
                btn_key = f"ff_{slot}_{s}"
                if col.button(f"{'✓ ' if winner==team else ''}{team[:18]}", key=btn_key,
                              disabled=(not t1 or not t2)):
                    st.session_state.final_four[slot] = team
                    if "champion" in st.session_state.final_four:
                        del st.session_state.final_four["champion"]
                    st.rerun()

        c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:4px;font-size:0.7rem;'>vs</div>", unsafe_allow_html=True)

        # Compare button for FF
        ff_key = ("ff", slot)
        is_exp = st.session_state.expanded_matchup == ff_key
        if t1 and t2:
            if c_cmp.button("▼ Compare" if not is_exp else "▲ Close", key=f"cmp_ff_{slot}"):
                st.session_state.expanded_matchup = None if is_exp else ff_key
                st.rerun()

        sf_winners[slot] = st.session_state.final_four.get(slot)

        # Show comparison if expanded
        if is_exp and t1 and t2:
            render_comparison_panel(t1, t2, "ff", slot, 0, df_stats)

        st.markdown("<br>", unsafe_allow_html=True)

    # Championship
    champ_t1 = sf_winners.get("sf1")
    champ_t2 = sf_winners.get("sf2")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;color:#fbbf24;letter-spacing:0.1em;">🏆 Championship</div>', unsafe_allow_html=True)
    c_a, c_vs, c_b, c_cmp = st.columns([4, 0.6, 4, 1.8])
    for col, team, s in [(c_a, champ_t1, 0), (c_b, champ_t2, 1)]:
        if not team:
            col.markdown('<div class="bracket-team tbd">TBD</div>', unsafe_allow_html=True)
        else:
            champ = st.session_state.final_four.get("champion")
            if col.button(f"{'🏆 ' if champ==team else ''}{team[:18]}", key=f"champ_{s}",
                          disabled=(not champ_t1 or not champ_t2)):
                st.session_state.final_four["champion"] = team
                st.rerun()
    c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:4px;font-size:0.7rem;'>vs</div>", unsafe_allow_html=True)
    ff_key = ("ff", "champ")
    is_exp = st.session_state.expanded_matchup == ff_key
    if champ_t1 and champ_t2:
        if c_cmp.button("▼ Compare" if not is_exp else "▲ Close", key="cmp_ff_champ"):
            st.session_state.expanded_matchup = None if is_exp else ff_key
            st.rerun()
        if is_exp:
            render_comparison_panel(champ_t1, champ_t2, "ff", "champ", 0, df_stats)

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
    st.markdown("# 🏀 Bracket Simulator")

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

    # ── Team entry ────────────────────────────────────────────────────────────
    with st.expander("📋 Fill In Your Bracket Teams", expanded=True):
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#64748b;margin-bottom:1rem;">Select the 64 teams for your bracket. In future versions this will be pre-filled from the official bracket.</div>', unsafe_allow_html=True)
        for region in REGIONS:
            st.markdown(f'<div class="region-header" style="font-size:1rem;">{region}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for i, seed in enumerate(SEEDS):
                col = cols[i % 4]
                current = st.session_state.bracket_teams[region].get(seed)
                idx = teams.index(current) + 1 if current in teams else 0
                sel = col.selectbox(
                    f"#{seed}",
                    [""] + teams,
                    index=idx,
                    key=f"entry_{region}_{seed}",
                    placeholder="Select team..."
                )
                st.session_state.bracket_teams[region][seed] = sel if sel else None

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Bracket ───────────────────────────────────────────────────────────────
    tabs = st.tabs(REGIONS + ["🏆 Final Four"])

    region_winners = {}
    for i, region in enumerate(REGIONS):
        with tabs[i]:
            winner = render_region(region, df_stats)
            region_winners[region] = winner

            # Show comparison panel if expanded for this region
            exp = st.session_state.expanded_matchup
            if exp and isinstance(exp, tuple) and len(exp) == 3 and exp[0] == region:
                _, r_idx, g_idx = exp
                t_a = get_team_in_slot(region, r_idx, g_idx, 0)
                t_b = get_team_in_slot(region, r_idx, g_idx, 1)
                if t_a and t_b:
                    render_comparison_panel(t_a, t_b, region, r_idx, g_idx, df_stats)

    with tabs[4]:
        render_final_four(df_stats)