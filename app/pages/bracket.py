"""
app/pages/bracket.py
====================
NCAA Tournament bracket simulator.
- All 4 regions on one page, pointing inward toward Final Four
- Native st.button for picks (no postMessage hacks)
- Season-aware: uses BRACKETS[season] from bracket_seeds
- Final Four pairings encoded per season
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

SEEDS             = list(range(1, 17))
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
ROUND_NAMES       = ["R64", "R32", "S16", "E8"]

# Final Four pairings per season: which two regions play each other
# Format: [(regionA, regionB), (regionC, regionD)]
# Left bracket: regionA (top) vs regionB (bottom)
# Right bracket: regionC (top) vs regionD (bottom)
FF_PAIRINGS = {
    2015: [("Midwest", "East"), ("South", "West")],
    2016: [("East", "West"), ("South", "Midwest")],
    2017: [("East", "Midwest"), ("West", "South")],
    2018: [("East", "Midwest"), ("South", "West")],
    2019: [("East", "West"), ("South", "Midwest")],
    2021: [("East", "West"), ("South", "Midwest")],
    2022: [("East", "Midwest"), ("West", "South")],
    2023: [("East", "Midwest"), ("West", "South")],
    2024: [("East", "West"), ("South", "Midwest")],
    2025: [("East", "Midwest"), ("West", "South")],
    2026: [("East", "South"), ("West", "Midwest")],
}

# ── Session state helpers ──────────────────────────────────────────────────────

def _key(season):
    return f"bracket_{season}"

def _init(season, bracket):
    k = _key(season)
    if k not in st.session_state:
        st.session_state[k] = {
            "teams":   {r: {s: bracket.get(r, {}).get(s) for s in SEEDS}
                        for r in bracket},
            "picks":   {},   # {region: {round: {game: team}}}
            "ff":      {},   # {matchup_idx: team}
            "champion": None,
        }

def _state(season):
    return st.session_state[_key(season)]

def get_winner(season, region, rnd, game):
    return _state(season)["picks"].get(region, {}).get(rnd, {}).get(game)

def set_winner(season, region, rnd, game, team):
    s = _state(season)
    s["picks"].setdefault(region, {}).setdefault(rnd, {})[game] = team
    _clear_downstream(s, region, rnd, game)

def _clear_downstream(s, region, rnd, game):
    nr, ng = rnd + 1, game // 2
    if s["picks"].get(region, {}).get(nr, {}).get(ng):
        del s["picks"][region][nr][ng]
        _clear_downstream(s, region, nr, ng)

def get_slot(season, region, rnd, game, slot):
    s = _state(season)
    if rnd == 0:
        seed = FIRST_ROUND_PAIRS[game][slot]
        return s["teams"].get(region, {}).get(seed)
    return get_winner(season, region, rnd - 1, game * 2 + slot)

def get_seed_for_slot(rnd, game, slot):
    return FIRST_ROUND_PAIRS[game][slot] if rnd == 0 else None

# ── CSS ────────────────────────────────────────────────────────────────────────

BRACKET_CSS = """
<style>
.bk-round-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #f97316;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
    padding-bottom: 4px;
}
.bk-matchup {
    background: #0d1526;
    border: 1px solid #1e2d45;
    border-radius: 5px;
    margin-bottom: 4px;
    overflow: hidden;
}
.bk-team {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    color: #94a3b8;
    border-bottom: 1px solid #1e2d45;
    min-height: 26px;
}
.bk-team:last-child { border-bottom: none; }
.bk-team.winner { color: #22c55e; background: #0a1f12; }
.bk-team.loser  { color: #334155; }
.bk-team.tbd    { color: #334155; font-style: italic; }
.bk-seed {
    font-size: 0.55rem;
    color: #475569;
    background: #1e3a5f;
    padding: 1px 4px;
    border-radius: 3px;
    min-width: 16px;
    text-align: center;
    flex-shrink: 0;
}
.bk-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.bk-region-label {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.1rem;
    color: #f97316;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
    border-left: 3px solid #f97316;
    padding-left: 8px;
}
.bk-ff-label {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 0.8rem;
    color: #64748b;
    letter-spacing: 0.08em;
    text-align: center;
    margin-bottom: 4px;
}
.bk-champ-banner {
    text-align: center;
    padding: 1.5rem;
    background: linear-gradient(135deg, #1a2c1a, #0f172a);
    border: 2px solid #fbbf24;
    border-radius: 12px;
    margin-top: 1rem;
}
/* Override Streamlit button styles for pick buttons */
.pick-btn > div > button {
    background: transparent !important;
    border: none !important;
    color: #475569 !important;
    font-size: 0.6rem !important;
    padding: 2px 6px !important;
    font-family: 'DM Mono', monospace !important;
    width: 100% !important;
    text-align: left !important;
}
.pick-btn > div > button:hover {
    background: rgba(249,115,22,0.1) !important;
    color: #f97316 !important;
}
</style>
"""

# ── Rendering helpers ──────────────────────────────────────────────────────────

def team_row(season, region, rnd, game, slot, mirror=False):
    """Render a single team row with pick button."""
    team   = get_slot(season, region, rnd, game, slot)
    winner = get_winner(season, region, rnd, game)
    other  = get_slot(season, region, rnd, game, 1 - slot)
    seed   = get_seed_for_slot(rnd, game, slot)

    if not team:
        st.markdown('<div class="bk-team tbd">TBD</div>', unsafe_allow_html=True)
        return

    is_winner = winner == team
    is_loser  = winner is not None and winner != team
    can_pick  = other is not None

    cls = "bk-team"
    if is_winner: cls += " winner"
    elif is_loser: cls += " loser"

    seed_html = f'<span class="bk-seed">{seed}</span>' if seed else '<span class="bk-seed" style="visibility:hidden">0</span>'
    icon = "✓" if is_winner else ("·" if not can_pick else "›")
    icon_color = "#22c55e" if is_winner else "#334155"

    st.markdown(
        f'<div class="{cls}">{seed_html}<span class="bk-name">{team}</span>'
        f'<span style="color:{icon_color};font-size:0.7rem;flex-shrink:0;">{icon}</span></div>',
        unsafe_allow_html=True
    )

    if can_pick:
        btn_label = f"{'✓ ' if is_winner else ''}Advance {team}"
        if st.button(btn_label, key=f"pick_{season}_{region}_{rnd}_{game}_{slot}",
                     use_container_width=True):
            set_winner(season, region, rnd, game, team)
            st.rerun()


def render_matchup_card(season, region, rnd, game, mirror=False):
    """Render a matchup card with two team rows."""
    with st.container():
        st.markdown('<div class="bk-matchup">', unsafe_allow_html=True)
        team_row(season, region, rnd, game, 0, mirror)
        team_row(season, region, rnd, game, 1, mirror)
        st.markdown('</div>', unsafe_allow_html=True)


def render_region_rounds(season, region, mirror=False):
    """
    Render 4 rounds for a region as columns.
    mirror=True reverses column order (right-side regions flow right→left).
    """
    rounds = []
    for rnd in range(4):
        num_games = 8 // (2 ** rnd)
        rounds.append((rnd, num_games))

    if mirror:
        rounds = list(reversed(rounds))

    cols = st.columns(4, gap="small")

    for col_idx, (rnd, num_games) in enumerate(rounds):
        with cols[col_idx]:
            actual_rnd = rnd
            st.markdown(f'<div class="bk-round-label">{ROUND_NAMES[actual_rnd]}</div>',
                        unsafe_allow_html=True)
            for game in range(num_games):
                render_matchup_card(season, region, actual_rnd, game, mirror)
                # Add spacing to align games across rounds
                spacers = (8 // num_games) - 1
                for _ in range(spacers):
                    st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)


def render_region_winner_slot(season, region, label="→ Final Four"):
    """Render the Elite 8 winner slot."""
    winner = get_winner(season, region, 3, 0)
    if winner:
        st.markdown(
            f'<div class="bk-matchup"><div class="bk-team winner">'
            f'<span class="bk-name">🏆 {winner}</span></div></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="bk-matchup"><div class="bk-team tbd">{label}</div></div>',
            unsafe_allow_html=True
        )


def render_ff_slot(season, matchup_idx, r1, r2, df_stats):
    """Render a Final Four semifinal matchup."""
    t1 = get_winner(season, r1, 3, 0)
    t2 = get_winner(season, r2, 3, 0)
    ff = _state(season)["ff"]
    picked = ff.get(matchup_idx)

    st.markdown(f'<div class="bk-ff-label">{r1} vs {r2}</div>', unsafe_allow_html=True)

    for i, (team, region) in enumerate([(t1, r1), (t2, r2)]):
        if not team:
            st.markdown('<div class="bk-matchup"><div class="bk-team tbd">TBD</div></div>',
                        unsafe_allow_html=True)
        else:
            is_winner = picked == team
            cls = "bk-team" + (" winner" if is_winner else "")
            st.markdown(
                f'<div class="bk-matchup"><div class="{cls}">'
                f'<span class="bk-name">{"✓ " if is_winner else ""}{team}</span></div></div>',
                unsafe_allow_html=True
            )
            if t1 and t2:
                if st.button(f"Advance {team}", key=f"ff_{season}_{matchup_idx}_{i}",
                             use_container_width=True):
                    ff[matchup_idx] = team
                    _state(season)["champion"] = None
                    st.rerun()


def render_championship(season, df_stats):
    """Render the championship matchup."""
    ff   = _state(season)["ff"]
    ct1  = ff.get(0)
    ct2  = ff.get(1)
    champ = _state(season).get("champion")

    st.markdown(
        '<div style="font-family:\'Bebas Neue\',sans-serif;font-size:0.9rem;'
        'color:#fbbf24;letter-spacing:0.1em;text-align:center;margin-bottom:4px;">'
        '🏆 CHAMPIONSHIP</div>',
        unsafe_allow_html=True
    )

    for i, team in enumerate([ct1, ct2]):
        if not team:
            st.markdown('<div class="bk-matchup"><div class="bk-team tbd">TBD</div></div>',
                        unsafe_allow_html=True)
        else:
            is_champ = champ == team
            cls = "bk-team" + (" winner" if is_champ else "")
            st.markdown(
                f'<div class="bk-matchup"><div class="{cls}">'
                f'<span class="bk-name">{"🏆 " if is_champ else ""}{team}</span></div></div>',
                unsafe_allow_html=True
            )
            if ct1 and ct2:
                if st.button(f"🏆 {team}", key=f"champ_{season}_{i}",
                             use_container_width=True):
                    _state(season)["champion"] = team
                    st.rerun()

    if champ:
        st.markdown(f"""
        <div class="bk-champ-banner">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:0.8rem;
                        color:#fbbf24;letter-spacing:0.2em;">YOUR CHAMPION</div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#fbbf24;">{champ}</div>
            <div style="font-size:1.5rem;">🏆</div>
        </div>""", unsafe_allow_html=True)


# ── Main show() ───────────────────────────────────────────────────────────────

def show(season: int):
    st.markdown(
        '<style>[data-testid="stAppViewContainer"],section.main,.block-container'
        '{background-color:#0a0f1e!important;}</style>',
        unsafe_allow_html=True
    )
    st.markdown(BRACKET_CSS, unsafe_allow_html=True)

    season_label = f"{season-1}–{str(season)[2:]}"
    st.markdown("# 🏆 Bracket Simulator")
    st.markdown(f'<div class="tag">Season {season_label}</div><br>', unsafe_allow_html=True)

    # Load bracket data
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "bracket_seeds",
            os.path.join(os.path.dirname(__file__), "..", "bracket_seeds.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        bracket = _mod.BRACKETS.get(season, {})
    except Exception as e:
        st.warning(f"Could not load bracket data: {e}")
        return

    if not bracket:
        st.info(f"No tournament bracket data for {season_label} (tournament may have been cancelled).")
        return

    _init(season, bracket)

    df_stats = db.get_team_data(season)
    game_df  = db.get_game_history(season)
    if not df_stats.empty:
        df_stats.columns = [c.lower() for c in df_stats.columns]
        if not game_df.empty:
            game_df.columns = [c.lower() for c in game_df.columns]
            nm.build(df_stats["team"].dropna().tolist(),
                     game_df["team"].dropna().unique().tolist())

    # Get Final Four pairings for this season
    pairings = FF_PAIRINGS.get(season, [("East", "South"), ("West", "Midwest")])
    left_top, left_bot   = pairings[0]
    right_top, right_bot = pairings[1]

    # Reset button
    if st.button("↺ Reset Bracket", key=f"reset_{season}"):
        k = _key(season)
        if k in st.session_state:
            del st.session_state[k]
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TOP ROW: left_top region (L→R) | center col | right_top region (R→L) ──
    left_col, center_col, right_col = st.columns([5, 2, 5], gap="small")

    with left_col:
        st.markdown(f'<div class="bk-region-label">{left_top}</div>', unsafe_allow_html=True)
        render_region_rounds(season, left_top, mirror=False)

    with right_col:
        st.markdown(f'<div class="bk-region-label" style="text-align:right;border-left:none;'
                    f'border-right:3px solid #f97316;padding-left:0;padding-right:8px;">'
                    f'{right_top}</div>', unsafe_allow_html=True)
        render_region_rounds(season, right_top, mirror=True)

    # Center top: E8 winners + FF semifinal top
    with center_col:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="small")
        with c1:
            render_region_winner_slot(season, left_top)
        with c2:
            render_region_winner_slot(season, right_top)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        render_ff_slot(season, 0, left_top, right_top, df_stats)

    st.markdown("<hr style='border-color:#1e2d45;margin:1rem 0;'>", unsafe_allow_html=True)

    # ── BOTTOM ROW: left_bot region | center col | right_bot region ──
    left_col2, center_col2, right_col2 = st.columns([5, 2, 5], gap="small")

    with left_col2:
        st.markdown(f'<div class="bk-region-label">{left_bot}</div>', unsafe_allow_html=True)
        render_region_rounds(season, left_bot, mirror=False)

    with right_col2:
        st.markdown(f'<div class="bk-region-label" style="text-align:right;border-left:none;'
                    f'border-right:3px solid #f97316;padding-left:0;padding-right:8px;">'
                    f'{right_bot}</div>', unsafe_allow_html=True)
        render_region_rounds(season, right_bot, mirror=True)

    with center_col2:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="small")
        with c1:
            render_region_winner_slot(season, left_bot)
        with c2:
            render_region_winner_slot(season, right_bot)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        render_ff_slot(season, 1, left_bot, right_bot, df_stats)

    st.markdown("<hr style='border-color:#1e2d45;margin:1rem 0;'>", unsafe_allow_html=True)

    # ── CHAMPIONSHIP ──────────────────────────────────────────────────────────
    _, champ_col, _ = st.columns([3, 2, 3])
    with champ_col:
        render_championship(season, df_stats)