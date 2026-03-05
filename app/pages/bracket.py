import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

REGIONS = ["East", "West", "South", "Midwest"]
SEEDS   = list(range(1, 17))
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
SEEDS_VERSION = "2026-v5"
ROUND_NAMES   = ["R64", "R32", "S16", "E8"]

# ── State helpers ─────────────────────────────────────────────────────────────
def init_bracket():
    if st.session_state.get("seeds_version") != SEEDS_VERSION:
        for k in ["bracket_teams","bracket_picks","final_four","expanded_matchup"]:
            st.session_state.pop(k, None)
        st.session_state.seeds_version = SEEDS_VERSION
    if "bracket_teams" not in st.session_state:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from bracket_seeds import BRACKET_2026
            st.session_state.bracket_teams = {
                r: {s: BRACKET_2026.get(r, {}).get(s) for s in SEEDS}
                for r in REGIONS
            }
        except Exception:
            st.session_state.bracket_teams = {r: {s: None for s in SEEDS} for r in REGIONS}
    if "bracket_picks"    not in st.session_state: st.session_state.bracket_picks    = {r: {} for r in REGIONS}
    if "final_four"       not in st.session_state: st.session_state.final_four       = {}
    if "expanded_matchup" not in st.session_state: st.session_state.expanded_matchup = None

def get_winner(region, round_idx, game_idx):
    return st.session_state.bracket_picks.get(region,{}).get(round_idx,{}).get(game_idx)

def set_winner(region, round_idx, game_idx, team):
    st.session_state.bracket_picks.setdefault(region,{}).setdefault(round_idx,{})[game_idx] = team
    clear_downstream(region, round_idx, game_idx)

def clear_downstream(region, round_idx, game_idx):
    picks = st.session_state.bracket_picks.get(region, {})
    nr, ng = round_idx + 1, game_idx // 2
    if nr in picks and ng in picks[nr]:
        del picks[nr][ng]
        clear_downstream(region, nr, ng)

def get_team_in_slot(region, round_idx, game_idx, slot):
    if round_idx == 0:
        return st.session_state.bracket_teams[region].get(FIRST_ROUND_PAIRS[game_idx][slot])
    return get_winner(region, round_idx - 1, game_idx * 2 + slot)

# ── Render region as a vertical round-by-round list using st.button ───────────
def render_region_col(region, df_stats):
    """Render one region as a compact vertical bracket using st.buttons."""
    st.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1rem;color:#f97316;letter-spacing:0.1em;margin-bottom:4px;">{region}</div>', unsafe_allow_html=True)

    for r in range(4):
        num_games = 8 // (2 ** r)
        st.markdown(f'<div style="font-family:monospace;font-size:0.55rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;border-left:2px solid #f97316;padding-left:4px;margin:4px 0 2px 0;">{ROUND_NAMES[r]}</div>', unsafe_allow_html=True)
        for g in range(num_games):
            ta = get_team_in_slot(region, r, g, 0)
            tb = get_team_in_slot(region, r, g, 1)
            winner = get_winner(region, r, g)

            for slot, team in [(0, ta), (1, tb)]:
                seed = FIRST_ROUND_PAIRS[g][slot] if r == 0 else None
                if not team:
                    st.markdown('<div style="height:22px;border:1px dashed #1a2d45;border-radius:3px;margin:1px 0;background:#080f1c;"></div>', unsafe_allow_html=True)
                    continue

                is_w = winner == team
                is_l = winner is not None and winner != team
                other = get_team_in_slot(region, r, g, 1 - slot)
                can_pick = other is not None

                seed_str = f"[{seed}] " if seed else ""
                label = f"{'✓ ' if is_w else ''}{seed_str}{team[:16]}"

                btn_style = ""
                if is_w:
                    btn_style = "color:#22c55e;"
                elif is_l:
                    btn_style = "opacity:0.4;"

                if can_pick:
                    clicked = st.button(label, key=f"p_{region}_{r}_{g}_{slot}",
                                        use_container_width=True)
                    if clicked:
                        set_winner(region, r, g, team)
                        st.rerun()
                else:
                    st.markdown(
                        f'<div style="font-size:11px;padding:3px 8px;border:1px solid #2d4a6b;'
                        f'border-radius:3px;background:#112240;color:#e2e8f0;margin:1px 0;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;{btn_style}">'
                        f'{label}</div>', unsafe_allow_html=True)

            # Compare button between team pairs
            if ta and tb:
                exp = st.session_state.expanded_matchup
                is_exp = exp == (region, r, g)
                cmp_label = "▲" if is_exp else "⚔"
                if st.button(cmp_label, key=f"cmp_{region}_{r}_{g}", help="Compare teams"):
                    st.session_state.expanded_matchup = None if is_exp else (region, r, g)
                    st.rerun()

            st.markdown('<div style="height:2px;"></div>', unsafe_allow_html=True)

    # Region winner
    e8w = get_winner(region, 3, 0)
    if e8w:
        st.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:0.8rem;color:#fbbf24;background:#1a2c1a;border:1px solid #fbbf24;border-radius:4px;padding:4px 8px;margin-top:4px;text-align:center;">🏆 {e8w}</div>', unsafe_allow_html=True)

def render_comparison_panel(team_a, team_b, region, round_idx, game_idx, df_stats):
    if df_stats.empty: return
    ra_rows = df_stats[df_stats["team"] == team_a]
    rb_rows = df_stats[df_stats["team"] == team_b]
    if ra_rows.empty or rb_rows.empty:
        st.info("Stats not available for one or both teams.")
        return

    import plotly.graph_objects as go
    ra, rb = ra_rows.iloc[0], rb_rows.iloc[0]

    def get_pct(val, col, hib=True):
        if val is None or pd.isna(val): return 0
        arr = pd.to_numeric(df_stats[col], errors="coerce").dropna().tolist()
        if not arr: return 0
        p = sum(v <= val for v in arr) / len(arr) * 100
        return p if hib else 100 - p

    radar_metrics = [
        ("Off. Eff.", "adj_oe", True), ("Def. Eff.", "adj_de", False),
        ("Tempo", "adj_tempo", True), ("eFG%", "efg_pct", True),
        ("TOV%", "tov_pct", False), ("ORB%", "orb_pct", True),
        ("FTR", "ftr", True), ("Opp eFG%", "opp_efg_pct", False),
    ]
    def row_pcts(row):
        out = []
        for _, col, hib in radar_metrics:
            v = row.get(col)
            v = float(v) if v is not None and not pd.isna(v) else None
            out.append(get_pct(v, col, hib) if v is not None else 0)
        return out

    labels = [m[0] for m in radar_metrics]
    pa, pb = row_pcts(ra), row_pcts(rb)
    lc = labels+[labels[0]]; pac = pa+[pa[0]]; pbc = pb+[pb[0]]

    st.markdown(f"### ⚔️ {team_a} vs {team_b}")
    rc1, rc2 = st.columns(2)

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=pac, theta=lc, fill="toself", name=team_a,
        line=dict(color="#f97316", width=2), fillcolor="rgba(249,115,22,0.15)"))
    fig.add_trace(go.Scatterpolar(r=pbc, theta=lc, fill="toself", name=team_b,
        line=dict(color="#06b6d4", width=2), fillcolor="rgba(6,182,212,0.15)"))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0,100], tickfont=dict(size=8, color="#475569"),
                gridcolor="#1e2d45", tickvals=[25,50,75,100], ticktext=["25%","50%","75%","100%"]),
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
            ("Adj OE", g(ra,"adj_oe",100), g(rb,"adj_oe",100), True,  ".1f"),
            ("Adj DE", g(ra,"adj_de",100), g(rb,"adj_de",100), False, ".1f"),
            ("eFG%",   g(ra,"efg_pct"),    g(rb,"efg_pct"),    True,  ".3f"),
            ("TOV%",   g(ra,"tov_pct"),    g(rb,"tov_pct"),    False, ".3f"),
            ("ORB%",   g(ra,"orb_pct"),    g(rb,"orb_pct"),    True,  ".3f"),
            ("Tempo",  g(ra,"adj_tempo",68), g(rb,"adj_tempo",68), True, ".1f"),
        ]:
            total = abs(va) + abs(vb)
            if total == 0: continue
            tp = abs(va) / total * 100
            better = (va > vb) if hib else (va < vb)
            tc = "#f97316" if better else "#64748b"
            oc = "#06b6d4" if not better else "#64748b"
            st.markdown(f"""<div style="margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                    font-size:0.65rem;color:#94a3b8;margin-bottom:3px;">
                    <span style="color:{tc};">{va:{fmt}}</span><span>{label}</span>
                    <span style="color:{oc};">{vb:{fmt}}</span></div>
                <div style="background:#1e2d45;border-radius:3px;height:8px;overflow:hidden;display:flex;">
                    <div style="width:{tp:.1f}%;background:{tc};"></div>
                    <div style="flex:1;background:{oc};"></div>
                </div></div>""", unsafe_allow_html=True)

    pb1, pb2 = st.columns(2)
    if pb1.button(f"🏆 Pick {team_a}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_0",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_a)
        st.session_state.expanded_matchup = (region, round_idx, game_idx)
        st.rerun()
    if pb2.button(f"🏆 Pick {team_b}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_1",
                  use_container_width=True):
        set_winner(region, round_idx, game_idx, team_b)
        st.session_state.expanded_matchup = (region, round_idx, game_idx)
        st.rerun()

def render_final_four(df_stats):
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.4rem;color:#f97316;letter-spacing:0.1em;">🏆 Final Four & Championship</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    sf_matchups = [("East","West","sf1"), ("South","Midwest","sf2")]
    sf_winners  = {}

    for r1, r2, slot in sf_matchups:
        t1 = get_winner(r1, 3, 0)
        t2 = get_winner(r2, 3, 0)
        st.markdown(f'<div style="font-family:monospace;font-size:0.65rem;color:#475569;text-transform:uppercase;margin-bottom:6px;">{r1} vs {r2}</div>', unsafe_allow_html=True)
        c_a, c_vs, c_b = st.columns([5, 0.5, 5])
        for col, team, s in [(c_a, t1, 0), (c_b, t2, 1)]:
            with col:
                if not team:
                    st.markdown('<div style="font-family:monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
                else:
                    winner = st.session_state.final_four.get(slot)
                    prefix = "✓ " if winner == team else ""
                    if st.button(f"{prefix}{team}", key=f"ff_{slot}_{s}",
                                 use_container_width=True, disabled=(not t1 or not t2)):
                        st.session_state.final_four[slot] = team
                        st.session_state.final_four.pop("champion", None)
                        st.rerun()
        c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:8px;'>vs</div>", unsafe_allow_html=True)
        sf_winners[slot] = st.session_state.final_four.get(slot)

        if t1 and t2:
            ff_key = ("ff", slot)
            is_exp = st.session_state.expanded_matchup == ff_key
            if st.button("▲ Close" if is_exp else "⚔ Compare", key=f"cmp_ff_{slot}"):
                st.session_state.expanded_matchup = None if is_exp else ff_key
                st.rerun()
            if is_exp:
                render_comparison_panel(t1, t2, "ff", slot, 0, df_stats)
        st.markdown("<br>", unsafe_allow_html=True)

    ct1, ct2 = sf_winners.get("sf1"), sf_winners.get("sf2")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;color:#fbbf24;letter-spacing:0.1em;">🏆 National Championship</div>', unsafe_allow_html=True)
    c_a, c_vs, c_b = st.columns([5, 0.5, 5])
    for col, team, s in [(c_a, ct1, 0), (c_b, ct2, 1)]:
        with col:
            if not team:
                st.markdown('<div style="font-family:monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
            else:
                champ  = st.session_state.final_four.get("champion")
                prefix = "🏆 " if champ == team else ""
                if st.button(f"{prefix}{team}", key=f"champ_{s}",
                             use_container_width=True, disabled=(not ct1 or not ct2)):
                    st.session_state.final_four["champion"] = team
                    st.rerun()
    c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:8px;'>vs</div>", unsafe_allow_html=True)

    if ct1 and ct2:
        ff_key = ("ff", "champ")
        is_exp = st.session_state.expanded_matchup == ff_key
        if st.button("▲ Close" if is_exp else "⚔ Compare", key="cmp_ff_champ"):
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
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    /* Make buttons compact for bracket */
    div[data-testid="stHorizontalBlock"] .stButton>button {
        padding: 2px 6px !important; font-size: 11px !important;
        min-height: 26px !important; height: 26px !important;
    }
    </style>""", unsafe_allow_html=True)
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

    tabs = st.tabs(["🏀 All Regions"] + REGIONS + ["🏆 Final Four"])

    # All regions tab
    with tabs[0]:
        col_e, col_w, col_s, col_m = st.columns(4)
        for col, region in zip([col_e, col_w, col_s, col_m], REGIONS):
            with col:
                render_region_col(region, df_stats)

        # Comparison panel (shown below all regions)
        exp = st.session_state.expanded_matchup
        if exp and isinstance(exp, tuple) and len(exp) == 3:
            region, r_idx, g_idx = exp
            t_a = get_team_in_slot(region, r_idx, g_idx, 0)
            t_b = get_team_in_slot(region, r_idx, g_idx, 1)
            if t_a and t_b:
                st.markdown("---")
                if st.button("✕ Close comparison", key="close_cmp_all"):
                    st.session_state.expanded_matchup = None
                    st.rerun()
                render_comparison_panel(t_a, t_b, region, r_idx, g_idx, df_stats)

    # Individual region tabs
    for i, region in enumerate(REGIONS):
        with tabs[i + 1]:
            render_region_col(region, df_stats)
            exp = st.session_state.expanded_matchup
            if exp and isinstance(exp, tuple) and len(exp) == 3 and exp[0] == region:
                _, r_idx, g_idx = exp
                t_a = get_team_in_slot(region, r_idx, g_idx, 0)
                t_b = get_team_in_slot(region, r_idx, g_idx, 1)
                if t_a and t_b:
                    st.markdown("---")
                    if st.button("✕ Close comparison", key=f"close_cmp_{region}"):
                        st.session_state.expanded_matchup = None
                        st.rerun()
                    render_comparison_panel(t_a, t_b, region, r_idx, g_idx, df_stats)

    with tabs[5]:
        render_final_four(df_stats)