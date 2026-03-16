import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm
from matchup import compute_win_prob, expected_score, DEFAULTS, logistic

MAX_SLOTS = 4

def init_state():
    if "cmp_slots" not in st.session_state:
        st.session_state.cmp_slots = [{"a": None, "b": None} for _ in range(MAX_SLOTS)]
    if "cmp_active" not in st.session_state:
        st.session_state.cmp_active = 1  # number of active slots

def get_weights():
    return {k: st.session_state.get(f"w_{k}", v) for k, v in DEFAULTS.items()}

def seed_buttons(teams, df, seed_map, bracket_seeds):
    """Render seed buttons 1-16 to auto-fill next empty slot."""
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">Quick add by seed matchup (1 vs 16, 2 vs 15...)</div>', unsafe_allow_html=True)
    SEED_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
    cols = st.columns(8)
    for i, (s1, s2) in enumerate(SEED_PAIRS):
        with cols[i]:
            label = f"{s1}v{s2}"
            if st.button(label, key=f"seed_btn_{s1}_{s2}", use_container_width=True):
                # Find teams for this seed pair across all regions (use first found)
                team_a, team_b = None, None
                for region, seeds in bracket_seeds.items():
                    if s1 in seeds and s2 in seeds:
                        team_a = seeds[s1]
                        team_b = seeds[s2]
                        break
                if team_a and team_b:
                    # Fill next available slot
                    active = st.session_state.cmp_active
                    for idx in range(active):
                        if not st.session_state.cmp_slots[idx]["a"] and not st.session_state.cmp_slots[idx]["b"]:
                            st.session_state.cmp_slots[idx] = {"a": team_a, "b": team_b}
                            st.rerun()
                    # All filled — add new slot if under max
                    if active < MAX_SLOTS:
                        st.session_state.cmp_active += 1
                        st.session_state.cmp_slots[active] = {"a": team_a, "b": team_b}
                        st.rerun()

def render_slot(idx, teams, df, game_df, weights, seed_map):
    slot = st.session_state.cmp_slots[idx]

    # Team pickers
    c1, cv, c2, cx = st.columns([5, 0.6, 5, 0.4])
    with c1:
        team_a = st.selectbox(
            f"Team A", teams,
            index=teams.index(slot["a"]) if slot["a"] in teams else None,
            placeholder="Search...", key=f"slot_{idx}_a", label_visibility="collapsed"
        )
    with cv:
        st.markdown("<div style='text-align:center;color:#334155;padding-top:0.4rem;font-size:1.1rem;'>vs</div>", unsafe_allow_html=True)
    with c2:
        team_b = st.selectbox(
            f"Team B", teams,
            index=teams.index(slot["b"]) if slot["b"] in teams else None,
            placeholder="Search...", key=f"slot_{idx}_b", label_visibility="collapsed"
        )
    with cx:
        if st.button("✕", key=f"slot_{idx}_clear", help="Clear this matchup"):
            st.session_state.cmp_slots[idx] = {"a": None, "b": None}
            st.rerun()

    # Sync back
    st.session_state.cmp_slots[idx] = {"a": team_a, "b": team_b}

    if not team_a or not team_b or team_a == team_b:
        return None

    ra = df[df["team"] == team_a]
    rb = df[df["team"] == team_b]
    if ra.empty or rb.empty:
        return None
    ra, rb = ra.iloc[0], rb.iloc[0]

    games_a = nm.get_team_games(game_df, df, team_a)
    games_b = nm.get_team_games(game_df, df, team_b)

    pa, pb = compute_win_prob(ra, rb, "Neutral", weights, games_a, games_b)

    def g(row, col, default=None):
        v = row.get(col)
        if v is None or (isinstance(v, float) and pd.isna(v)): return default
        try: return float(v)
        except: return default

    return {
        "team_a": team_a, "team_b": team_b,
        "pa": pa, "pb": pb,
        "seed_a": seed_map.get(team_a), "seed_b": seed_map.get(team_b),
        "record_a": ra.get("record","—"), "record_b": rb.get("record","—"),
        "oe_a": g(ra,"adj_oe"), "oe_b": g(rb,"adj_oe"),
        "de_a": g(ra,"adj_de"), "de_b": g(rb,"adj_de"),
        "net_a": g(ra,"net_eff"), "net_b": g(rb,"net_eff"),
        "efg_a": g(ra,"efg_pct"), "efg_b": g(rb,"efg_pct"),
        "tov_a": g(ra,"tov_pct"), "tov_b": g(rb,"tov_pct"),
        "orb_a": g(ra,"orb_pct"), "orb_b": g(rb,"orb_pct"),
        "tempo_a": g(ra,"adj_tempo",68), "tempo_b": g(rb,"adj_tempo",68),
        "sos_a": g(ra,"sos_oe"), "sos_b": g(rb,"sos_oe"),
    }

def win_prob_card(result):
    pa, pb = result["pa"], result["pb"]
    ca = "#f97316" if pa >= pb else "#64748b"
    cb = "#f97316" if pb > pa else "#64748b"
    favored = result["team_a"] if pa >= pb else result["team_b"]
    seed_a = f'<span style="font-size:0.7rem;color:#64748b;"> #{result["seed_a"]}</span>' if result["seed_a"] else ""
    seed_b = f'<span style="font-size:0.7rem;color:#64748b;"> #{result["seed_b"]}</span>' if result["seed_b"] else ""
    return f"""
    <div style="background:#111827;border:1px solid #1e2d45;border-radius:8px;padding:1rem;margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
            <div style="text-align:left;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;">{result["team_a"]}{seed_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:{ca};">{pa*100:.0f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.55rem;color:#475569;">{result["record_a"]}</div>
            </div>
            <div style="text-align:center;color:#334155;font-size:0.8rem;">vs</div>
            <div style="text-align:right;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;">{result["team_b"]}{seed_b}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:{cb};">{pb*100:.0f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.55rem;color:#475569;">{result["record_b"]}</div>
            </div>
        </div>
        <div style="background:#1e2d45;border-radius:4px;height:8px;overflow:hidden;display:flex;">
            <div style="width:{pa*100:.1f}%;background:{ca};border-radius:4px 0 0 4px;"></div>
            <div style="flex:1;background:#334155;border-radius:0 4px 4px 0;"></div>
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:#475569;margin-top:4px;text-align:center;">
            Favored: <span style="color:#f97316;">{favored}</span>
        </div>
    </div>"""

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# 📊 Matchup Comparison")

    init_state()

    df      = db.get_team_data()
    teams   = db.team_list()
    game_df = db.get_game_history()

    if df.empty or not teams:
        st.warning("No data yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]
    if not game_df.empty:
        game_df.columns = [c.lower() for c in game_df.columns]
        nm.build(df["team"].dropna().tolist(), game_df["team"].dropna().unique().tolist())

    # Build seed map
    seed_map = {}
    bracket_seeds = {}
    try:
        from bracket_seeds import BRACKET_2026
        bracket_seeds = BRACKET_2026
        for region, seeds in BRACKET_2026.items():
            for seed, team in seeds.items():
                if team: seed_map[team] = seed
    except Exception:
        pass

    weights = get_weights()

    # ── Seed quick-add buttons ────────────────────────────────────────────────
    seed_buttons(teams, df, seed_map, bracket_seeds)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Slot controls ─────────────────────────────────────────────────────────
    ctrl_l, ctrl_r = st.columns([6, 1])
    with ctrl_l:
        active = st.session_state.cmp_active
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;">{active} of {MAX_SLOTS} matchups</div>', unsafe_allow_html=True)
    with ctrl_r:
        if st.session_state.cmp_active < MAX_SLOTS:
            if st.button("＋ Add", key="add_slot"):
                st.session_state.cmp_active += 1
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Render slots & collect results ───────────────────────────────────────
    results = []
    for idx in range(st.session_state.cmp_active):
        with st.container():
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#475569;text-transform:uppercase;margin-bottom:4px;">Matchup {idx+1}</div>', unsafe_allow_html=True)
            result = render_slot(idx, teams, df, game_df, weights, seed_map)
            if result:
                results.append(result)
        st.markdown("---")

    if not results:
        return

    # ── Headline cards ────────────────────────────────────────────────────────
    st.markdown("### Win Probabilities")
    card_cols = st.columns(len(results))
    for i, (col, r) in enumerate(zip(card_cols, results)):
        with col:
            st.markdown(win_prob_card(r), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Comparison table ──────────────────────────────────────────────────────
    st.markdown("### Detailed Stats Comparison")

    STATS = [
        ("Win Prob", "pa", "pb", True, ".0%"),
        ("Adj. Off. Eff.", "oe_a", "oe_b", True, ".1f"),
        ("Adj. Def. Eff.", "de_a", "de_b", False, ".1f"),
        ("Net Efficiency", "net_a", "net_b", True, ".1f"),
        ("eFG%", "efg_a", "efg_b", True, ".3f"),
        ("TOV%", "tov_a", "tov_b", False, ".3f"),
        ("Off. Reb%", "orb_a", "orb_b", True, ".3f"),
        ("Tempo", "tempo_a", "tempo_b", True, ".1f"),
        ("SOS", "sos_a", "sos_b", True, ".1f"),
    ]

    def fmt_val(v, fmt):
        if v is None: return "—"
        if fmt == ".0%": return f"{v*100:.0f}%"
        return f"{v:{fmt}}"

    def edge_color(va, vb, higher_is_better):
        if va is None or vb is None: return "#475569", "#475569"
        better_a = (va > vb) if higher_is_better else (va < vb)
        return ("#f97316", "#475569") if better_a else ("#475569", "#f97316")

    # Build header
    header_html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-family:\'DM Mono\',monospace;font-size:0.7rem;">'
    header_html += '<thead><tr style="border-bottom:1px solid #1e2d45;">'
    header_html += '<th style="text-align:left;padding:8px 12px;color:#475569;text-transform:uppercase;letter-spacing:0.08em;">Stat</th>'
    for r in results:
        header_html += f'<th colspan="2" style="text-align:center;padding:8px 12px;color:#f1f5f9;border-left:1px solid #1e2d45;">{r["team_a"]} vs {r["team_b"]}</th>'
    header_html += '</tr>'
    header_html += '<tr style="border-bottom:2px solid #1e2d45;">'
    header_html += '<th></th>'
    for r in results:
        header_html += f'<th style="text-align:center;padding:4px 12px;color:#64748b;border-left:1px solid #1e2d45;">{r["team_a"]}</th>'
        header_html += f'<th style="text-align:center;padding:4px 12px;color:#64748b;">{r["team_b"]}</th>'
    header_html += '</tr></thead><tbody>'

    # Build rows
    for label, key_a, key_b, hib, fmt in STATS:
        row_html = f'<tr style="border-bottom:1px solid #0f172a;">'
        row_html += f'<td style="padding:8px 12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;">{label}</td>'
        for r in results:
            va = r.get(key_a)
            vb = r.get(key_b)
            ca, cb = edge_color(va, vb, hib)
            row_html += f'<td style="text-align:center;padding:8px 12px;color:{ca};border-left:1px solid #1e2d45;">{fmt_val(va, fmt)}</td>'
            row_html += f'<td style="text-align:center;padding:8px 12px;color:{cb};">{fmt_val(vb, fmt)}</td>'
        row_html += '</tr>'
        header_html += row_html

    header_html += '</tbody></table></div>'
    st.markdown(header_html, unsafe_allow_html=True)