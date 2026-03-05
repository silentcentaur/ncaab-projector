import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

REGIONS = ["East", "West", "South", "Midwest"]
SEEDS   = list(range(1, 17))
# seed pairs for R64: (top_seed, bottom_seed)
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]

SEEDS_VERSION = "2026-v3"

DARK_CSS = """<style>
[data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
</style>"""

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG        = "#0a0f1e"
C_SLOT_BG   = "#112240"
C_SLOT_WIN  = "#0f2d1a"
C_SLOT_BORDER = "#2d4a6b"
C_WIN_BORDER  = "#22c55e"
C_LINE      = "#1e3a5f"
C_TEXT      = "#e2e8f0"
C_TEXT_WIN  = "#22c55e"
C_TEXT_SEED = "#64748b"
C_ORANGE    = "#f97316"
C_TBD       = "#334155"
C_HOVER     = "#1a3255"

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

    if "bracket_picks" not in st.session_state:
        st.session_state.bracket_picks = {r: {} for r in REGIONS}
    if "final_four" not in st.session_state:
        st.session_state.final_four = {}
    if "expanded_matchup" not in st.session_state:
        st.session_state.expanded_matchup = None

def get_winner(region, round_idx, game_idx):
    return st.session_state.bracket_picks.get(region,{}).get(round_idx,{}).get(game_idx)

def set_winner(region, round_idx, game_idx, team):
    bp = st.session_state.bracket_picks
    bp.setdefault(region, {}).setdefault(round_idx, {})[game_idx] = team
    clear_downstream(region, round_idx, game_idx)

def clear_downstream(region, round_idx, game_idx):
    picks = st.session_state.bracket_picks.get(region, {})
    nr, ng = round_idx + 1, game_idx // 2
    if nr in picks and ng in picks[nr]:
        del picks[nr][ng]
        clear_downstream(region, nr, ng)

def get_team_in_slot(region, round_idx, game_idx, slot):
    if round_idx == 0:
        seed = FIRST_ROUND_PAIRS[game_idx][slot]
        return st.session_state.bracket_teams[region].get(seed)
    return get_winner(region, round_idx - 1, game_idx * 2 + slot)

# ── Bracket geometry ──────────────────────────────────────────────────────────
# Layout constants
SLOT_W      = 140   # width of a team slot box
SLOT_H      = 22    # height of a team slot box
SLOT_GAP    = 4     # gap between the two teams in a matchup
ROUND_GAP   = 50    # horizontal gap between rounds
NUM_ROUNDS  = 4     # R64 → R32 → S16 → E8

def round_x(r):
    """Left x of round r (0=R64)."""
    return r * (SLOT_W + ROUND_GAP)

def matchup_positions(round_idx):
    """
    Return list of (cx, top_y) for each game in the round.
    cx = left edge of the slot, top_y = y of the top team slot.
    Games are evenly spaced vertically.
    """
    num_games = 8 // (2 ** round_idx)
    # Each matchup occupies a vertical band
    # Total height we want to fill
    total_h = 8 * (2 * SLOT_H + SLOT_GAP + 20)  # 8 R64 matchups worth of space
    band = total_h / num_games
    cx = round_x(round_idx)
    positions = []
    for g in range(num_games):
        center_y = band * g + band / 2
        top_y = center_y - (SLOT_H + SLOT_GAP / 2)
        positions.append((cx, top_y))
    return positions

def build_bracket_figure(region, df_stats):
    """Build a Plotly figure for one region's bracket."""
    positions_by_round = [matchup_positions(r) for r in range(NUM_ROUNDS)]
    total_h = 8 * (2 * SLOT_H + SLOT_GAP + 20)
    total_w = round_x(NUM_ROUNDS) + 20

    shapes = []
    annotations = []
    # clickable_slots: list of dicts with text=team, region, round, game, slot
    # We encode these in customdata of scatter points
    scatter_x, scatter_y, scatter_custom = [], [], []

    def add_slot(x, y, w, h, team, seed, is_winner, is_loser, region, round_idx, game_idx, slot):
        bg    = C_SLOT_WIN  if is_winner else C_SLOT_BG
        border= C_WIN_BORDER if is_winner else C_SLOT_BORDER
        tc    = C_TEXT_WIN  if is_winner else (C_TBD if not team else C_TEXT)
        alpha = 0.35 if is_loser else 1.0

        # Box
        shapes.append(dict(
            type="rect", x0=x, y0=-(y+h), x1=x+w, y1=-y,
            fillcolor=bg, line=dict(color=border, width=1),
            opacity=alpha,
        ))

        label = team if team else "TBD"
        seed_str = f"{seed} " if seed and round_idx == 0 else ""

        # Seed number (small, left side)
        if seed and round_idx == 0:
            annotations.append(dict(
                x=x+6, y=-(y + h/2),
                text=f"<b>{seed}</b>",
                font=dict(size=9, color=C_TEXT_SEED, family="DM Mono"),
                showarrow=False, xanchor="left", yanchor="middle",
                opacity=alpha,
            ))
            text_x = x + 22
        else:
            text_x = x + 8

        # Team name
        annotations.append(dict(
            x=text_x, y=-(y + h/2),
            text=label,
            font=dict(size=11, color=tc, family="DM Sans"),
            showarrow=False, xanchor="left", yanchor="middle",
            opacity=alpha,
        ))

        # Invisible scatter point for click detection
        if team and team != "TBD":
            scatter_x.append(x + w/2)
            scatter_y.append(-(y + h/2))
            scatter_custom.append({
                "region": region, "round": round_idx,
                "game": game_idx, "slot": slot, "team": team
            })

    def add_connector(r, g, pos_this, pos_next):
        """Draw the bracket connector line from this round to the next."""
        cx, top_y = pos_this
        mid_y_top = top_y + SLOT_H / 2       # center of top team
        mid_y_bot = top_y + SLOT_H + SLOT_GAP + SLOT_H / 2  # center of bottom team
        mid_y     = (mid_y_top + mid_y_bot) / 2

        right_x   = cx + SLOT_W
        next_cx, next_top_y = pos_next
        # next slot center y
        next_mid_y = next_top_y + SLOT_H / 2 if g % 2 == 0 else next_top_y + SLOT_H + SLOT_GAP + SLOT_H / 2

        # Horizontal line right from slot
        shapes.append(dict(type="line",
            x0=right_x, y0=-mid_y, x1=right_x + ROUND_GAP/2, y1=-mid_y,
            line=dict(color=C_LINE, width=1.5)))
        # Vertical joining line
        if g % 2 == 0:
            next_g = g // 2
            nx, ny = positions_by_round[r+1][next_g]
            top_join    = positions_by_round[r][g][1] + SLOT_H / 2
            bot_join_g  = g + 1
            if bot_join_g < len(positions_by_round[r]):
                bot_join = positions_by_round[r][bot_join_g][1] + SLOT_H / 2
                shapes.append(dict(type="line",
                    x0=right_x + ROUND_GAP/2, y0=-top_join,
                    x1=right_x + ROUND_GAP/2, y1=-bot_join,
                    line=dict(color=C_LINE, width=1.5)))
                # Horizontal line into next slot
                next_mid = (top_join + bot_join) / 2
                shapes.append(dict(type="line",
                    x0=right_x + ROUND_GAP/2, y0=-next_mid,
                    x1=next_cx, y1=-next_mid,
                    line=dict(color=C_LINE, width=1.5)))

    # Draw all matchups
    for r in range(NUM_ROUNDS):
        positions = positions_by_round[r]
        num_games = len(positions)
        for g in range(num_games):
            cx, top_y = positions[g]
            winner = get_winner(region, r, g)
            for slot in range(2):
                team  = get_team_in_slot(region, r, g, slot)
                seed  = FIRST_ROUND_PAIRS[g][slot] if r == 0 else None
                y_off = 0 if slot == 0 else SLOT_H + SLOT_GAP
                is_w  = (winner == team and team is not None)
                is_l  = (winner is not None and winner != team and team is not None)
                add_slot(cx, top_y + y_off, SLOT_W, SLOT_H,
                         team, seed, is_w, is_l, region, r, g, slot)

            # Connector to next round
            if r < NUM_ROUNDS - 1:
                add_connector(r, g, positions[g], positions_by_round[r+1])

    # Elite 8 winner slot (rightmost)
    e8_winner = get_winner(region, 3, 0)
    ex = round_x(NUM_ROUNDS)
    ey = total_h / 2 - SLOT_H / 2
    shapes.append(dict(
        type="rect", x0=ex, y0=-(ey+SLOT_H), x1=ex+SLOT_W, y1=-ey,
        fillcolor=C_SLOT_WIN if e8_winner else C_SLOT_BG,
        line=dict(color=C_WIN_BORDER if e8_winner else C_ORANGE, width=2),
    ))
    annotations.append(dict(
        x=ex+8, y=-(ey+SLOT_H/2),
        text=e8_winner or "→ Final Four",
        font=dict(size=11, color=C_WIN_BORDER if e8_winner else C_ORANGE, family="DM Sans"),
        showarrow=False, xanchor="left", yanchor="middle",
    ))
    # Connector from E8 to winner box
    e8_pos = positions_by_round[3][0]
    e8_mid = e8_pos[1] + SLOT_H / 2
    shapes.append(dict(type="line",
        x0=round_x(3)+SLOT_W, y0=-e8_mid,
        x1=ex, y1=-(ey+SLOT_H/2),
        line=dict(color=C_LINE, width=1.5)))

    # Round labels
    round_names = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]
    for r, name in enumerate(round_names):
        annotations.append(dict(
            x=round_x(r) + SLOT_W/2, y=10,
            text=name.upper(),
            font=dict(size=9, color=C_ORANGE, family="DM Mono"),
            showarrow=False, xanchor="center", yanchor="bottom",
        ))

    # Scatter for click targets
    fig = go.Figure()
    if scatter_x:
        fig.add_trace(go.Scatter(
            x=scatter_x, y=scatter_y,
            mode="markers",
            marker=dict(size=SLOT_H, opacity=0, symbol="square"),
            customdata=scatter_custom,
            hovertemplate="%{customdata.team}<extra></extra>",
        ))

    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        xaxis=dict(visible=False, range=[-10, total_w + SLOT_W + 10]),
        yaxis=dict(visible=False, range=[-(total_h + 20), 20]),
        margin=dict(l=10, r=10, t=30, b=10),
        height=max(600, int(total_h) + 50),
        showlegend=False,
        dragmode=False,
    )
    return fig

def render_comparison_panel(team_a, team_b, region, round_idx, game_idx, df_stats):
    if df_stats.empty: return
    ra_rows = df_stats[df_stats["team"] == team_a]
    rb_rows = df_stats[df_stats["team"] == team_b]
    if ra_rows.empty or rb_rows.empty:
        st.info("Stats not available for one or both teams.")
        return

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
    lc = labels + [labels[0]]; pac = pa + [pa[0]]; pbc = pb + [pb[0]]

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
            ("Adj OE", g(ra,"adj_oe",100), g(rb,"adj_oe",100), True, ".1f"),
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

def render_region_tab(region, df_stats):
    st.markdown(f'<div style="font-family:Bebas Neue,sans-serif;font-size:1.4rem;color:#f97316;letter-spacing:0.1em;">{region} Region</div>', unsafe_allow_html=True)

    fig = build_bracket_figure(region, df_stats)
    click = st.plotly_chart(fig, use_container_width=True, on_select="rerun",
                            selection_mode="points", key=f"bracket_{region}")

    # Handle click
    if click and click.selection and click.selection.points:
        pt = click.selection.points[0]
        cd = pt.get("customdata", {})
        if isinstance(cd, dict) and "team" in cd:
            clicked_team  = cd["team"]
            r_idx = cd["round"]; g_idx = cd["game"]; slot = cd["slot"]
            other_slot = 1 - slot
            other_team = get_team_in_slot(region, r_idx, g_idx, other_slot)
            if other_team:  # can only pick if opponent is set
                set_winner(region, r_idx, g_idx, clicked_team)
                st.session_state.expanded_matchup = (region, r_idx, g_idx)
                st.rerun()

    # Comparison panel
    exp = st.session_state.expanded_matchup
    if exp and isinstance(exp, tuple) and len(exp) == 3 and exp[0] == region:
        _, r_idx, g_idx = exp
        t_a = get_team_in_slot(region, r_idx, g_idx, 0)
        t_b = get_team_in_slot(region, r_idx, g_idx, 1)
        if t_a and t_b:
            st.markdown("---")
            col_close, _ = st.columns([1, 8])
            if col_close.button("✕ Close", key=f"close_cmp_{region}"):
                st.session_state.expanded_matchup = None
                st.rerun()
            render_comparison_panel(t_a, t_b, region, r_idx, g_idx, df_stats)

def render_final_four(df_stats):
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.8rem;color:#f97316;letter-spacing:0.1em;text-align:center;">🏆 FINAL FOUR & CHAMPIONSHIP</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    sf_matchups = [("East","West","sf1"), ("South","Midwest","sf2")]
    sf_winners  = {}

    for r1, r2, slot in sf_matchups:
        t1 = get_winner(r1, 3, 0)
        t2 = get_winner(r2, 3, 0)
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.7rem;color:#475569;text-transform:uppercase;margin-bottom:6px;">{r1} Champion vs {r2} Champion</div>', unsafe_allow_html=True)
        c_a, c_vs, c_b = st.columns([5, 0.5, 5])
        for col, team, s in [(c_a, t1, 0), (c_b, t2, 1)]:
            with col:
                if not team:
                    st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
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

        # Compare button
        if t1 and t2:
            ff_key = ("ff", slot)
            is_exp = st.session_state.expanded_matchup == ff_key
            if st.button("▲ Close comparison" if is_exp else "▼ Compare", key=f"cmp_ff_{slot}"):
                st.session_state.expanded_matchup = None if is_exp else ff_key
                st.rerun()
            if is_exp:
                render_comparison_panel(t1, t2, "ff", slot, 0, df_stats)
        st.markdown("<br>", unsafe_allow_html=True)

    # Championship
    ct1, ct2 = sf_winners.get("sf1"), sf_winners.get("sf2")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;color:#fbbf24;letter-spacing:0.1em;">🏆 National Championship</div>', unsafe_allow_html=True)
    c_a, c_vs, c_b = st.columns([5, 0.5, 5])
    for col, team, s in [(c_a, ct1, 0), (c_b, ct2, 1)]:
        with col:
            if not team:
                st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
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
        if st.button("▲ Close comparison" if is_exp else "▼ Compare", key="cmp_ff_champ"):
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

    tabs = st.tabs(REGIONS + ["🏆 Final Four"])
    for i, region in enumerate(REGIONS):
        with tabs[i]:
            render_region_tab(region, df_stats)
    with tabs[4]:
        render_final_four(df_stats)