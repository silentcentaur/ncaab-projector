import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm
import bracket_seeds as bs
from pages.matchup import compute_win_prob, compute_upset_signals, confidence_label, expected_score, DEFAULTS, logistic

MAX_SLOTS = 4

def init_state():
    if "cmp_slots" not in st.session_state:
        st.session_state.cmp_slots = [{"a": None, "b": None} for _ in range(MAX_SLOTS)]
    # Always ensure 4 slots exist
    while len(st.session_state.cmp_slots) < MAX_SLOTS:
        st.session_state.cmp_slots.append({"a": None, "b": None})

def get_weights():
    return {k: st.session_state.get(f"w_{k}", v) for k, v in DEFAULTS.items()}

def seed_buttons(teams, df, seed_map, bracket_seeds):
    """Render seed pair buttons — clicking fills all 4 slots with that matchup across all regions."""
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">Load all 4 regional matchups by seed pairing</div>', unsafe_allow_html=True)
    SEED_PAIRS = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
    REGIONS = ["East","West","South","Midwest"]
    cols = st.columns(8)
    for i, (s1, s2) in enumerate(SEED_PAIRS):
        with cols[i]:
            if st.button(f"{s1}v{s2}", key=f"seed_btn_{s1}_{s2}", use_container_width=True):
                new_slots = []
                for region in REGIONS:
                    seeds = bracket_seeds.get(region, {})
                    ta = seeds.get(s1)
                    tb = seeds.get(s2)
                    new_slots.append({"a": ta, "b": tb})
                # Pad to 4 slots if fewer than 4 regions returned valid pairs
                while len(new_slots) < MAX_SLOTS:
                    new_slots.append({"a": None, "b": None})
                st.session_state.cmp_slots = new_slots
                # Write directly to selectbox keys to override cached widget state
                for i, slot in enumerate(new_slots):
                    st.session_state[f"slot_{i}_a"] = slot["a"]
                    st.session_state[f"slot_{i}_b"] = slot["b"]
                st.rerun()

def render_slot(idx, teams, df, game_df, weights, seed_map):
    slot = st.session_state.cmp_slots[idx]

    # Pre-populate session state keys so selectbox reflects seeded values
    key_a, key_b = f"slot_{idx}_a", f"slot_{idx}_b"
    if slot["a"] and slot["a"] in teams:
        st.session_state[key_a] = slot["a"]
    elif not slot["a"]:
        st.session_state[key_a] = None
    if slot["b"] and slot["b"] in teams:
        st.session_state[key_b] = slot["b"]
    elif not slot["b"]:
        st.session_state[key_b] = None

    # Team pickers
    c1, cv, c2, cx = st.columns([5, 0.6, 5, 0.4])
    with c1:
        team_a = st.selectbox(
            "Team A", [None] + teams,
            format_func=lambda x: "Search..." if x is None else x,
            key=key_a, label_visibility="collapsed"
        )
    with cv:
        st.markdown("<div style='text-align:center;color:#334155;padding-top:0.4rem;font-size:1.1rem;'>vs</div>", unsafe_allow_html=True)
    with c2:
        team_b = st.selectbox(
            "Team B", [None] + teams,
            format_func=lambda x: "Search..." if x is None else x,
            key=key_b, label_visibility="collapsed"
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

    pa_base, pb_base = compute_win_prob(ra, rb, "Neutral", weights, games_a, games_b)

    # Derive rank from net_eff across full dataset
    df["_net_eff_num"] = pd.to_numeric(df["net_eff"], errors="coerce")
    df["_rank"] = df["_net_eff_num"].rank(ascending=False, method="min").astype("Int64")
    rank_a = int(df.loc[df["team"] == team_a, "_rank"].iloc[0]) if team_a in df["team"].values else None
    rank_b = int(df.loc[df["team"] == team_b, "_rank"].iloc[0]) if team_b in df["team"].values else None

    seed_a_val, _ = bs.get_seed(team_a)
    seed_b_val, _ = bs.get_seed(team_b)
    # Fall back to seed_map (built from bracket) if get_seed misses
    if seed_a_val is None: seed_a_val = seed_map.get(team_a)
    if seed_b_val is None: seed_b_val = seed_map.get(team_b)

    adjustment, _ = compute_upset_signals(ra, rb, games_a, games_b,
                                          seed_override_a=seed_a_val,
                                          seed_override_b=seed_b_val,
                                          rank_override_a=rank_a,
                                          rank_override_b=rank_b)
    pa = round(float(np.clip(pa_base + adjustment, 0.05, 0.95)), 4)
    pb = round(1 - pa, 4)

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
    tier_label, tier_color = confidence_label(pa)
    return f"""
    <div style="background:#111827;border:1px solid #1e2d45;border-radius:8px;padding:1rem;margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
            <div style="text-align:left;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;">{result["team_a"]}{seed_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:{ca};">{pa*100:.0f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.55rem;color:#475569;">{result["record_a"]}</div>
            </div>
            <div style="text-align:center;">
                <div style="display:inline-block;padding:3px 10px;border-radius:20px;
                            background:{tier_color}22;border:1px solid {tier_color}66;
                            font-family:'DM Mono',monospace;font-size:0.55rem;
                            color:{tier_color};letter-spacing:0.06em;margin-bottom:6px;">
                    {tier_label.upper()}
                </div>
                <div style="color:#334155;font-size:0.8rem;">vs</div>
            </div>
            <div style="text-align:right;">
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;">{result["team_b"]}{seed_b}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:{cb};">{pb*100:.0f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.55rem;color:#475569;">{result["record_b"]}</div>
            </div>
        </div>
        <div style="background:#1e2d45;border-radius:4px;height:8px;overflow:hidden;display:flex;">
            <div style="width:{pa*100:.1f}%;background:{ca};border-radius:4px 0 0 4px;"></div>
            <div style="flex:1;background:{cb};border-radius:0 4px 4px 0;"></div>
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

    # Build seed map — force fresh import to avoid stale module cache
    seed_map = {}
    bracket_seeds_dict = {}
    try:
        import importlib
        import bracket_seeds as _bs_fresh
        importlib.reload(_bs_fresh)
        bracket_seeds_dict = _bs_fresh.BRACKET_2026
        for region, seeds in _bs_fresh.BRACKET_2026.items():
            for seed, team in seeds.items():
                if team:
                    seed_map[team] = seed
    except Exception as e:
        st.warning(f"Could not load bracket seeds: {e}")

    if not seed_map:
        st.warning("Seed map is empty — check bracket_seeds.py is accessible.")

    weights = get_weights()

    # ── Seed quick-add buttons ────────────────────────────────────────────────
    seed_buttons(teams, df, seed_map, bracket_seeds_dict)
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Render slots & collect results ───────────────────────────────────────
    results = []
    for idx in range(MAX_SLOTS):
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