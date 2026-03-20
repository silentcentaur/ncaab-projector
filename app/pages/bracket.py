import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm

REGIONS = ["East", "West", "South", "Midwest"]
SEEDS   = list(range(1, 17))
FIRST_ROUND_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
SEEDS_VERSION = "2026-v9"
ROUND_NAMES   = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]

def init_bracket():
    if st.session_state.get("seeds_version") != SEEDS_VERSION:
        for k in ["bracket_teams","bracket_picks","final_four","expanded_matchup"]:
            st.session_state.pop(k, None)
        st.session_state.seeds_version = SEEDS_VERSION
    if "bracket_teams" not in st.session_state:
        try:
            from bracket_seeds import BRACKET_2026
            st.session_state.bracket_teams = {
                r: {s: BRACKET_2026.get(r,{}).get(s) for s in SEEDS} for r in REGIONS
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

def team_html(region, round_idx, game_idx, slot):
    team   = get_team_in_slot(region, round_idx, game_idx, slot)
    winner = get_winner(region, round_idx, game_idx)
    other  = get_team_in_slot(region, round_idx, game_idx, 1 - slot)
    seed   = FIRST_ROUND_PAIRS[game_idx][slot] if round_idx == 0 else None

    if not team:
        return '<div class="team tbd">TBD</div>'

    is_winner = winner == team
    is_loser  = winner is not None and winner != team
    can_pick  = other is not None

    cls = "team"
    if is_winner: cls += " winner"
    elif is_loser: cls += " loser"
    if can_pick:  cls += " pickable"

    seed_html = f'<span class="seed">{seed}</span>' if seed else ''
    pick_payload = f"{region}|{round_idx}|{game_idx}|{slot}|pick"
    onclick = f"sendClick('{pick_payload}')" if can_pick else ""
    title   = "Click to pick winner" if can_pick else ""

    return f'<div class="{cls}" onclick="{onclick}" title="{title}">{seed_html}<span class="name">{team}</span></div>'

def build_region_rounds(region):
    rounds_html = ""
    for r in range(4):
        num_games = 8 // (2**r)
        matchups_html = ""
        for g in range(num_games):
            ta = get_team_in_slot(region, r, g, 0)
            tb = get_team_in_slot(region, r, g, 1)
            can_compare = ta is not None and tb is not None
            cmp_payload = f"{region}|{r}|{g}|cmp"
            exp = st.session_state.expanded_matchup
            is_expanded = exp == (region, r, g)
            cmp_btn = ""
            if can_compare:
                cmp_label = "▲" if is_expanded else "⚔"
                cmp_btn = f'<button class="cmp-btn" onclick="sendClick(\'{cmp_payload}\')" title="Compare teams">{cmp_label}</button>'
            matchups_html += f'''
            <div class="matchup">
                <div class="matchup-teams">
                    {team_html(region, r, g, 0)}
                    {team_html(region, r, g, 1)}
                </div>
                {cmp_btn}
            </div>'''
        rounds_html += f'''
        <div class="round">
            <div class="round-label">{ROUND_NAMES[r]}</div>
            <div class="round-games">{matchups_html}</div>
        </div>'''
    e8_winner = get_winner(region, 3, 0)
    winner_slot = f'<div class="team winner"><span class="name">🏆 {e8_winner}</span></div>' if e8_winner else '<div class="team tbd">→ Final Four</div>'
    rounds_html += f'''
    <div class="round final-slot">
        <div class="round-label">Region Winner</div>
        <div class="round-games"><div class="matchup"><div class="matchup-teams">{winner_slot}</div></div></div>
    </div>'''
    return rounds_html

def build_bracket_html(regions):
    if isinstance(regions, str):
        regions = [regions]

    CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0a0f1e; font-family: 'DM Sans', sans-serif; overflow-x: auto; padding: 8px; }
.all-regions { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; min-width: max-content; }
.region-block { display: flex; flex-direction: column; }
.region-title { font-family: 'Bebas Neue', cursive; font-size: 0.9rem; color: #f97316;
                letter-spacing: 0.1em; margin-bottom: 6px; padding-left: 4px; border-left: 3px solid #f97316; padding-left: 6px; }
.bracket { display: flex; flex-direction: row; align-items: stretch; }
.round { display: flex; flex-direction: column; min-width: 170px; }
.round-label { font-family: monospace; font-size: 10px; color: #f97316; text-transform: uppercase;
               letter-spacing: 0.1em; padding: 0 8px 8px 8px; text-align: center; white-space: nowrap; }
.round-games { display: flex; flex-direction: column; flex: 1; justify-content: space-around; }
.matchup { display: flex; flex-direction: row; align-items: center; flex: 1; padding: 3px 0; }
.matchup-teams { display: flex; flex-direction: column; gap: 2px; }
.team { display: flex; align-items: center; gap: 6px; width: 155px; height: 26px;
        padding: 0 8px; border-radius: 4px; border: 1px solid #2d4a6b;
        background: #112240; color: #e2e8f0; font-size: 11px;
        white-space: nowrap; overflow: hidden; font-family: 'DM Mono', monospace; }
.team.tbd { color: #334155; border-color: #1a2d45; border-style: dashed; background: #080f1c; }
.team.winner { background: #0f2d1a; border-color: #22c55e; color: #22c55e; }
.team.loser  { opacity: 0.35; }
.team.pickable { cursor: pointer; transition: all 0.1s; }
.team.pickable:hover { background: #1a3255; border-color: #f97316; color: #f1f5f9; }
.team.winner.pickable:hover { background: #143d22; border-color: #4ade80; }
.seed { font-size: 9px; color: #64748b; background: #1e3a5f; padding: 1px 4px;
        border-radius: 3px; min-width: 18px; text-align: center; flex-shrink: 0; }
.name { overflow: hidden; text-overflow: ellipsis; }
.cmp-btn { background: none; border: 1px solid #1e3a5f; color: #475569; cursor: pointer;
           font-size: 11px; padding: 2px 6px; border-radius: 3px; margin-left: 4px;
           transition: all 0.1s; }
.cmp-btn:hover { border-color: #f97316; color: #f97316; }
.final-slot .team { border-color: #f97316; background: #1a1200; color: #fbbf24; }
"""

    JS = """
function sendClick(payload) {
    window.parent.postMessage({type: 'streamlit:setComponentValue', value: payload}, '*');
}
"""

    blocks = ""
    for region in regions:
        rounds_html = build_region_rounds(region)
        blocks += f'''
        <div class="region-block">
            <div class="region-title">{region} Region</div>
            <div class="bracket">{rounds_html}</div>
        </div>'''

    return f"""<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans&family=DM+Mono&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head><body>
<div class="all-regions">{blocks}</div>
<script>{JS}</script>
</body></html>"""

def render_comparison_panel(team_a, team_b, region, round_idx, game_idx, df_stats):
    st.markdown(f"""
    <div style="background:#0d1526;border:1px solid #1e2d45;border-radius:8px;padding:1.25rem;margin:0.75rem 0;">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f97316;margin-bottom:0.75rem;letter-spacing:0.05em;">
            ⚔ {team_a} vs {team_b}
        </div>""", unsafe_allow_html=True)

    if df_stats.empty:
        st.markdown("No stats available.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    ra = df_stats[df_stats["team"] == team_a]
    rb = df_stats[df_stats["team"] == team_b]

    def gv(row_df, col, default=0.0):
        if row_df.empty: return default
        v = row_df.iloc[0].get(col)
        if v is None or (isinstance(v, float) and pd.isna(v)): return default
        try: return float(v)
        except: return default

    net_a = gv(ra,"net_eff"); net_b = gv(rb,"net_eff")
    ca = "#f97316" if net_a >= net_b else "#64748b"
    cb = "#f97316" if net_b > net_a  else "#64748b"

    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1rem;color:{ca};">{team_a}</div>', unsafe_allow_html=True)
        st.metric("Net Eff", f"{net_a:+.1f}")
        st.metric("Adj OE",  f"{gv(ra,'adj_oe',100):.1f}")
        st.metric("Adj DE",  f"{gv(ra,'adj_de',100):.1f}")
    with rc2:
        st.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1rem;color:{cb};text-align:right;">{team_b}</div>', unsafe_allow_html=True)
        st.metric("Net Eff", f"{net_b:+.1f}")
        st.metric("Adj OE",  f"{gv(rb,'adj_oe',100):.1f}")
        st.metric("Adj DE",  f"{gv(rb,'adj_de',100):.1f}")

    rc2b = st.columns(2)
    with rc2b[0]:
        for label, va, vb, hib, fmt in [
            ("Adj OE", gv(ra,"adj_oe",100), gv(rb,"adj_oe",100), True,  ".1f"),
            ("Adj DE", gv(ra,"adj_de",100), gv(rb,"adj_de",100), False, ".1f"),
            ("eFG%",   gv(ra,"efg_pct"),    gv(rb,"efg_pct"),    True,  ".3f"),
            ("TOV%",   gv(ra,"tov_pct"),    gv(rb,"tov_pct"),    False, ".3f"),
            ("ORB%",   gv(ra,"orb_pct"),    gv(rb,"orb_pct"),    True,  ".3f"),
            ("Tempo",  gv(ra,"adj_tempo",68), gv(rb,"adj_tempo",68), True, ".1f"),
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
    if pb1.button(f"🏆 Pick {team_a}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_0", use_container_width=True):
        set_winner(region, round_idx, game_idx, team_a)
        st.session_state.expanded_matchup = (region, round_idx, game_idx)
        st.rerun()
    if pb2.button(f"🏆 Pick {team_b}", key=f"cmp_pick_{region}_{round_idx}_{game_idx}_1", use_container_width=True):
        set_winner(region, round_idx, game_idx, team_b)
        st.session_state.expanded_matchup = (region, round_idx, game_idx)
        st.rerun()

def render_region_tab(region, df_stats, all_regions=False):
    regions = REGIONS if all_regions else [region]
    html    = build_bracket_html(regions)
    height  = 1320 if all_regions else 620
    click   = components.html(html, height=height, scrolling=True)

    if click and isinstance(click, str) and "|" in click:
        parts = click.split("|")
        if len(parts) == 5 and parts[4] == "pick":
            r_reg, r_idx, g_idx, slot = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
            team  = get_team_in_slot(r_reg, r_idx, g_idx, slot)
            other = get_team_in_slot(r_reg, r_idx, g_idx, 1 - slot)
            if team and other:
                set_winner(r_reg, r_idx, g_idx, team)
                st.rerun()
        elif len(parts) == 4 and parts[3] == "cmp":
            r_reg, r_idx, g_idx = parts[0], int(parts[1]), int(parts[2])
            key = (r_reg, r_idx, g_idx)
            st.session_state.expanded_matchup = None if st.session_state.expanded_matchup == key else key
            st.rerun()

    exp = st.session_state.expanded_matchup
    if exp and isinstance(exp, tuple) and len(exp) == 3:
        exp_region, r_idx, g_idx = exp
        if exp_region in regions:
            t_a = get_team_in_slot(exp_region, r_idx, g_idx, 0)
            t_b = get_team_in_slot(exp_region, r_idx, g_idx, 1)
            if t_a and t_b:
                st.markdown("---")
                close_key = "close_cmp_all" if all_regions else f"close_cmp_{region}"
                if st.button("✕ Close", key=close_key):
                    st.session_state.expanded_matchup = None
                    st.rerun()
                render_comparison_panel(t_a, t_b, exp_region, r_idx, g_idx, df_stats)

def render_final_four(df_stats):
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.8rem;color:#f97316;letter-spacing:0.1em;text-align:center;">🏆 FINAL FOUR & CHAMPIONSHIP</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    for r1, r2, slot in [("East","South","sf1"), ("West","Midwest","sf2")]:
        t1 = get_winner(r1, 3, 0); t2 = get_winner(r2, 3, 0)
        st.markdown(f'<div style="font-family:monospace;font-size:0.7rem;color:#475569;text-transform:uppercase;margin-bottom:6px;">{r1} Champion vs {r2} Champion</div>', unsafe_allow_html=True)
        c_a, c_vs, c_b = st.columns([5, 0.5, 5])
        for col, team, s in [(c_a,t1,0),(c_b,t2,1)]:
            with col:
                if not team:
                    st.markdown('<div style="font-family:monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
                else:
                    w = st.session_state.final_four.get(slot)
                    if st.button(f"{'✓ ' if w==team else ''}{team}", key=f"ff_{slot}_{s}", use_container_width=True, disabled=(not t1 or not t2)):
                        st.session_state.final_four[slot] = team
                        st.session_state.final_four.pop("champion", None)
                        st.rerun()
        c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:8px;'>vs</div>", unsafe_allow_html=True)
        ff_key = ("ff", slot); is_exp = st.session_state.expanded_matchup == ff_key
        if t1 and t2:
            if st.button("▲ Close" if is_exp else "⚔ Compare", key=f"cmp_ff_{slot}"):
                st.session_state.expanded_matchup = None if is_exp else ff_key
                st.rerun()
            if is_exp: render_comparison_panel(t1, t2, "ff", slot, 0, df_stats)
        st.markdown("<br>", unsafe_allow_html=True)

    ct1 = st.session_state.final_four.get("sf1"); ct2 = st.session_state.final_four.get("sf2")
    st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;color:#fbbf24;letter-spacing:0.1em;">🏆 National Championship</div>', unsafe_allow_html=True)
    c_a, c_vs, c_b = st.columns([5, 0.5, 5])
    for col, team, s in [(c_a,ct1,0),(c_b,ct2,1)]:
        with col:
            if not team:
                st.markdown('<div style="font-family:monospace;font-size:0.8rem;color:#334155;padding:8px 12px;border:1px dashed #1e3a5f;border-radius:5px;">TBD</div>', unsafe_allow_html=True)
            else:
                champ = st.session_state.final_four.get("champion")
                if st.button(f"{'🏆 ' if champ==team else ''}{team}", key=f"champ_{s}", use_container_width=True, disabled=(not ct1 or not ct2)):
                    st.session_state.final_four["champion"] = team
                    st.rerun()
    c_vs.markdown("<div style='text-align:center;color:#334155;padding-top:8px;'>vs</div>", unsafe_allow_html=True)
    ff_key = ("ff","champ"); is_exp = st.session_state.expanded_matchup == ff_key
    if ct1 and ct2:
        if st.button("▲ Close" if is_exp else "⚔ Compare", key="cmp_ff_champ"):
            st.session_state.expanded_matchup = None if is_exp else ff_key
            st.rerun()
        if is_exp: render_comparison_panel(ct1, ct2, "ff", "champ", 0, df_stats)

    champ = st.session_state.final_four.get("champion")
    if champ:
        st.markdown(f"""<div style="text-align:center;margin-top:2rem;padding:2rem;
            background:linear-gradient(135deg,#1a2c1a,#0f172a);border:2px solid #fbbf24;border-radius:12px;">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;color:#fbbf24;letter-spacing:0.2em;">YOUR CHAMPION</div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:2.5rem;color:#fbbf24;">{champ}</div>
            <div style="font-size:2rem;">🏆</div></div>""", unsafe_allow_html=True)

def show(season: int):
    st.markdown('<style>[data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}</style>', unsafe_allow_html=True)
    st.markdown("# 🏆 Bracket Simulator")
    init_bracket()

    df_stats = db.get_team_data(season)
    game_df  = db.get_game_history(season)
    if not df_stats.empty:
        df_stats.columns = [c.lower() for c in df_stats.columns]
        if not game_df.empty:
            game_df.columns = [c.lower() for c in game_df.columns]
            nm.build(df_stats["team"].dropna().tolist(),
                     game_df["team"].dropna().unique().tolist())

    tabs = st.tabs(["🏀 All Regions"] + REGIONS + ["🏆 Final Four"])
    with tabs[0]:
        render_region_tab("East", df_stats, all_regions=True)
    for i, region in enumerate(REGIONS):
        with tabs[i + 1]:
            render_region_tab(region, df_stats)
    with tabs[5]:
        render_final_four(df_stats)