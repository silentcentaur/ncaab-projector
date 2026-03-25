"""
app/pages/bracket.py
====================
NCAA Tournament bracket simulator.
- Clean matchup cards with two team pick buttons each
- 2x2 layout pointing inward toward Final Four
- Season-aware
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

SEEDS             = list(range(1, 17))
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
ROUND_NAMES       = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]

FF_PAIRINGS = {
    2015: [("Midwest", "East"),   ("South", "West")],
    2016: [("East", "West"),      ("South", "Midwest")],
    2017: [("East", "Midwest"),   ("West", "South")],
    2018: [("East", "Midwest"),   ("South", "West")],
    2019: [("East", "West"),      ("South", "Midwest")],
    2021: [("East", "West"),      ("South", "Midwest")],
    2022: [("East", "Midwest"),   ("West", "South")],
    2023: [("East", "Midwest"),   ("West", "South")],
    2024: [("East", "West"),      ("South", "Midwest")],
    2025: [("East", "Midwest"),   ("West", "South")],
    2026: [("East", "South"),     ("West", "Midwest")],
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Bebas+Neue&display=swap');

.bk-region {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.1rem;
    color: #f97316;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
    padding-left: 8px;
    border-left: 3px solid #f97316;
}
.bk-region.right {
    text-align: right;
    padding-left: 0;
    padding-right: 8px;
    border-left: none;
    border-right: 3px solid #f97316;
}
.bk-round-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.58rem;
    color: #f97316;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
    margin-bottom: 6px;
}
.bk-card {
    background: #0d1526;
    border: 1px solid #1e2d45;
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 6px;
}
.bk-card-team {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    color: #94a3b8;
    border-bottom: 1px solid #1e2d45;
    min-height: 28px;
    cursor: default;
}
.bk-card-team.last { border-bottom: none; }
.bk-card-team.winner { color: #22c55e; background: #071a0e; }
.bk-card-team.loser  { color: #2d3f52; }
.bk-card-team.tbd    { color: #2d3f52; font-style: italic; }
.bk-seed {
    font-size: 0.55rem;
    color: #475569;
    background: #1a2d45;
    padding: 1px 4px;
    border-radius: 3px;
    min-width: 18px;
    text-align: center;
    flex-shrink: 0;
}
.bk-teamname { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bk-pick-row {
    display: flex;
    border-top: 1px solid #1e2d45;
    background: #080f1c;
}
.bk-tbd-card {
    background: #080f1c;
    border: 1px dashed #1a2d45;
    border-radius: 6px;
    padding: 8px;
    margin-bottom: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #1e3a5f;
    text-align: center;
}
.bk-ff-header {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    text-align: center;
    margin-bottom: 4px;
}
.bk-champ {
    text-align: center;
    padding: 1.5rem 1rem;
    background: linear-gradient(135deg, #1a2c1a, #0f172a);
    border: 2px solid #fbbf24;
    border-radius: 10px;
    margin-top: 0.5rem;
}
div[data-testid="stButton"] > button {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.6rem !important;
    padding: 0px 4px !important;
    height: 28px !important;
    min-height: 28px !important;
    line-height: 28px !important;
    border-radius: 4px !important;
}
/* Remove extra padding Streamlit wraps around buttons */
div[data-testid="stButton"] {
    margin: 0 !important;
    padding: 0 !important;
}
</style>
"""

# ── State helpers ─────────────────────────────────────────────────────────────

def _k(season): return f"bk_{season}"

def _init(season, bracket):
    k = _k(season)
    if k not in st.session_state:
        st.session_state[k] = {
            "teams":    {r: {s: bracket.get(r, {}).get(s) for s in SEEDS} for r in bracket},
            "picks":    {},
            "ff":       {},
            "champion": None,
        }

def _s(season): return st.session_state[_k(season)]

def get_winner(season, region, rnd, game):
    return _s(season)["picks"].get(region, {}).get(rnd, {}).get(game)

def set_winner(season, region, rnd, game, team):
    s = _s(season)
    s["picks"].setdefault(region, {}).setdefault(rnd, {})[game] = team
    _cascade(s, region, rnd, game)

def _cascade(s, region, rnd, game):
    nr, ng = rnd + 1, game // 2
    if s["picks"].get(region, {}).get(nr, {}).get(ng):
        del s["picks"][region][nr][ng]
        _cascade(s, region, nr, ng)

def get_slot(season, region, rnd, game, slot):
    if rnd == 0:
        return _s(season)["teams"].get(region, {}).get(FIRST_ROUND_PAIRS[game][slot])
    return get_winner(season, region, rnd - 1, game * 2 + slot)

# ── Matchup card ──────────────────────────────────────────────────────────────

def matchup_card(season, region, rnd, game):
    ta = get_slot(season, region, rnd, game, 0)
    tb = get_slot(season, region, rnd, game, 1)
    winner = get_winner(season, region, rnd, game)
    sa = FIRST_ROUND_PAIRS[game][0] if rnd == 0 else None
    sb = FIRST_ROUND_PAIRS[game][1] if rnd == 0 else None
    can_pick = ta is not None and tb is not None

    if not ta and not tb:
        st.markdown('<div class="bk-tbd-card">TBD</div>', unsafe_allow_html=True)
        return

    # Render card HTML + inline pick buttons per team row
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    for slot, (team, seed) in enumerate([(ta, sa), (tb, sb)]):
        is_last = slot == 1
        is_win  = winner == team if team else False
        is_lose = (winner is not None and winner != team) if team else False

        if not team:
            st.markdown(
                f'<div class="bk-card-team tbd{" last" if is_last else ""}">'
                f'<span class="bk-teamname">TBD</span></div>',
                unsafe_allow_html=True)
            continue

        cls = "bk-card-team"
        if is_win:  cls += " winner"
        if is_lose: cls += " loser"
        if is_last: cls += " last"
        seed_html = f'<span class="bk-seed">{seed}</span>' if seed else ''
        icon = "✓" if is_win else ""

        # Team info + pick button side by side
        team_col, btn_col = st.columns([6, 1], gap="small")
        with team_col:
            st.markdown(
                f'<div class="{cls}">{seed_html}'
                f'<span class="bk-teamname">{team}</span>'
                f'<span style="color:#22c55e;font-size:0.65rem;flex-shrink:0;">{icon}</span>'
                f'</div>',
                unsafe_allow_html=True)
        with btn_col:
            if can_pick:
                btn_style = "primary" if is_win else "secondary"
                if st.button("▶", key=f"p_{season}_{region}_{rnd}_{game}_{slot}",
                             use_container_width=True, type=btn_style):
                    set_winner(season, region, rnd, game, team)
                    st.rerun()
            else:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

        if not is_last:
            st.markdown("<div style='height:1px;background:#1e2d45;margin:0;'></div>",
                        unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def region_winner_card(season, region):
    winner = get_winner(season, region, 3, 0)
    if winner:
        st.markdown(
            f'<div class="bk-card"><div class="bk-card-team winner last">'
            f'<span class="bk-teamname">🏆 {winner}</span></div></div>',
            unsafe_allow_html=True)
    else:
        st.markdown('<div class="bk-tbd-card">→ Final Four</div>', unsafe_allow_html=True)


def ff_card(season, matchup_idx, r1, r2):
    t1 = get_winner(season, r1, 3, 0)
    t2 = get_winner(season, r2, 3, 0)
    picked = _s(season)["ff"].get(matchup_idx)

    st.markdown(f'<div class="bk-ff-header">{r1} vs {r2}</div>', unsafe_allow_html=True)

    def ff_team_row(team, is_last=False):
        if not team:
            cls = "bk-card-team tbd" + (" last" if is_last else "")
            return f'<div class="{cls}"><span class="bk-teamname">TBD</span></div>'
        is_win = picked == team
        cls = "bk-card-team" + (" winner" if is_win else "") + (" last" if is_last else "")
        icon = "✓" if is_win else ""
        return (f'<div class="{cls}"><span class="bk-teamname">{team}</span>'
                f'<span style="color:#22c55e;font-size:0.7rem;">{icon}</span></div>')

    st.markdown(
        f'<div class="bk-card">{ff_team_row(t1)}{ff_team_row(t2, is_last=True)}</div>',
        unsafe_allow_html=True)

    if t1 and t2:
        for i, team in enumerate([t1, t2]):
            is_picked = picked == team
            tc, bc = st.columns([6, 1], gap="small")
            with tc:
                cls = "bk-card-team" + (" winner" if is_picked else "") + (" last" if i==1 else "")
                icon = "✓" if is_picked else ""
                st.markdown(
                    f'<div class="{cls}"><span class="bk-teamname">{team}</span>'
                    f'<span style="color:#22c55e;font-size:0.65rem;">{icon}</span></div>',
                    unsafe_allow_html=True)
            with bc:
                if st.button("▶", key=f"ff_{season}_{matchup_idx}_{i}",
                             use_container_width=True,
                             type="primary" if is_picked else "secondary"):
                    _s(season)["ff"][matchup_idx] = team
                    _s(season)["champion"] = None
                    st.rerun()
            if i == 0:
                st.markdown("<div style='height:1px;background:#1e2d45;margin:0;'></div>",
                            unsafe_allow_html=True)


def champ_card(season):
    ct1 = _s(season)["ff"].get(0)
    ct2 = _s(season)["ff"].get(1)
    champ = _s(season).get("champion")

    st.markdown(
        '<div style="font-family:\'Bebas Neue\',sans-serif;font-size:0.9rem;'
        'color:#fbbf24;letter-spacing:0.1em;text-align:center;margin-bottom:4px;">'
        '🏆 CHAMPIONSHIP</div>',
        unsafe_allow_html=True)

    def champ_row(team, is_last=False):
        if not team:
            cls = "bk-card-team tbd" + (" last" if is_last else "")
            return f'<div class="{cls}"><span class="bk-teamname">TBD</span></div>'
        is_win = champ == team
        cls = "bk-card-team" + (" winner" if is_win else "") + (" last" if is_last else "")
        icon = "🏆" if is_win else ""
        return (f'<div class="{cls}"><span class="bk-teamname">{team}</span>'
                f'<span style="color:#fbbf24;font-size:0.7rem;">{icon}</span></div>')

    st.markdown(
        f'<div class="bk-card">{champ_row(ct1)}{champ_row(ct2, is_last=True)}</div>',
        unsafe_allow_html=True)

    if ct1 and ct2:
        for i, team in enumerate([ct1, ct2]):
            is_champ = champ == team
            tc, bc = st.columns([6, 1], gap="small")
            with tc:
                cls = "bk-card-team" + (" winner" if is_champ else "") + (" last" if i==1 else "")
                icon = "🏆" if is_champ else ""
                st.markdown(
                    f'<div class="{cls}"><span class="bk-teamname">{team}</span>'
                    f'<span style="color:#fbbf24;font-size:0.65rem;">{icon}</span></div>',
                    unsafe_allow_html=True)
            with bc:
                if st.button("▶", key=f"champ_{season}_{i}",
                             use_container_width=True,
                             type="primary" if is_champ else "secondary"):
                    _s(season)["champion"] = team
                    st.rerun()
            if i == 0:
                st.markdown("<div style='height:1px;background:#1e2d45;margin:0;'></div>",
                            unsafe_allow_html=True)

    if champ:
        st.markdown(f"""
        <div class="bk-champ">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:0.75rem;
                color:#fbbf24;letter-spacing:0.2em;">YOUR CHAMPION</div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1.8rem;
                color:#fbbf24;">{champ}</div>
            <div>🏆</div>
        </div>""", unsafe_allow_html=True)


def render_region(season, region, mirror=False):
    """Render 4 rounds of a region as columns, optionally mirrored."""
    rounds = list(range(4))
    if mirror:
        rounds = list(reversed(rounds))

    cols = st.columns(4, gap="small")
    for col_i, rnd in enumerate(rounds):
        num_games = 8 // (2 ** rnd)
        with cols[col_i]:
            st.markdown(f'<div class="bk-round-label">{ROUND_NAMES[rnd]}</div>',
                        unsafe_allow_html=True)
            for game in range(num_games):
                matchup_card(season, region, rnd, game)
                # Vertical spacers to distribute games evenly
                spacers = (8 // num_games) - 1
                for _ in range(spacers):
                    st.markdown("<div style='height:34px'></div>",
                                unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def show(season: int):
    st.markdown(
        '<style>[data-testid="stAppViewContainer"],section.main,.block-container'
        '{background-color:#0a0f1e!important;}</style>',
        unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)

    season_label = f"{season-1}–{str(season)[2:]}"
    st.markdown("# 🏆 Bracket Simulator")
    st.markdown(f'<div class="tag">Season {season_label}</div><br>',
                unsafe_allow_html=True)

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bracket_seeds",
            os.path.join(os.path.dirname(__file__), "..", "bracket_seeds.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        bracket = mod.BRACKETS.get(season, {})
    except Exception as e:
        st.warning(f"Could not load bracket data: {e}")
        return

    if not bracket:
        st.info(f"No tournament data for {season_label}.")
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

    pairings = FF_PAIRINGS.get(season, [("East", "South"), ("West", "Midwest")])
    lt, lb = pairings[0]   # left top, left bottom
    rt, rb = pairings[1]   # right top, right bottom

    col_reset, _ = st.columns([2, 8])
    with col_reset:
        if st.button("↺ Reset", key=f"reset_{season}"):
            if _k(season) in st.session_state:
                del st.session_state[_k(season)]
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TOP HALF ──────────────────────────────────────────────────────────────
    lc, cc, rc = st.columns([10, 3, 10], gap="small")

    with lc:
        st.markdown(f'<div class="bk-region">{lt}</div>', unsafe_allow_html=True)
        render_region(season, lt, mirror=False)

    with rc:
        st.markdown(f'<div class="bk-region right">{rt}</div>', unsafe_allow_html=True)
        render_region(season, rt, mirror=True)

    with cc:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        lc2, rc2 = st.columns(2, gap="small")
        with lc2:
            region_winner_card(season, lt)
        with rc2:
            region_winner_card(season, rt)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        ff_card(season, 0, lt, rt)

    st.markdown("<hr style='border-color:#1e2d45;margin:1.5rem 0;'>",
                unsafe_allow_html=True)

    # ── BOTTOM HALF ───────────────────────────────────────────────────────────
    lc3, cc3, rc3 = st.columns([10, 3, 10], gap="small")

    with lc3:
        st.markdown(f'<div class="bk-region">{lb}</div>', unsafe_allow_html=True)
        render_region(season, lb, mirror=False)

    with rc3:
        st.markdown(f'<div class="bk-region right">{rb}</div>', unsafe_allow_html=True)
        render_region(season, rb, mirror=True)

    with cc3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        lc4, rc4 = st.columns(2, gap="small")
        with lc4:
            region_winner_card(season, lb)
        with rc4:
            region_winner_card(season, rb)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        ff_card(season, 1, lb, rb)

    st.markdown("<hr style='border-color:#1e2d45;margin:1.5rem 0;'>",
                unsafe_allow_html=True)

    # ── CHAMPIONSHIP ──────────────────────────────────────────────────────────
    _, cc5, _ = st.columns([4, 3, 4])
    with cc5:
        champ_card(season)