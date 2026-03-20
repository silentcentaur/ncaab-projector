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
    while len(st.session_state.cmp_slots) < MAX_SLOTS:
        st.session_state.cmp_slots.append({"a": None, "b": None})

def get_weights():
    return {k: st.session_state.get(f"w_{k}", v) for k, v in DEFAULTS.items()}

def seed_buttons(teams, df, seed_map, bracket_seeds):
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
                while len(new_slots) < MAX_SLOTS:
                    new_slots.append({"a": None, "b": None})
                st.session_state.cmp_slots = new_slots
                for i, slot in enumerate(new_slots):
                    st.session_state[f"slot_{i}_a"] = slot["a"]
                    st.session_state[f"slot_{i}_b"] = slot["b"]
                    st.session_state[f"slot_{i}_seeded"] = True
                st.rerun()

def render_slot(idx, teams, df, game_df, weights, seed_map):
    slot = st.session_state.cmp_slots[idx]

    key_a, key_b = f"slot_{idx}_a", f"slot_{idx}_b"
    seed_flag = f"slot_{idx}_seeded"

    if st.session_state.get(seed_flag):
        if slot["a"] and slot["a"] in teams:
            st.session_state[key_a] = slot["a"]
        if slot["b"] and slot["b"] in teams:
            st.session_state[key_b] = slot["b"]
        st.session_state[seed_flag] = False

    c1, cv, c2 = st.columns([5, 1, 5])
    with c1:
        team_a = st.selectbox(f"Team A (Matchup {idx+1})", teams,
                              index=teams.index(st.session_state[key_a]) if st.session_state.get(key_a) in teams else None,
                              placeholder="Type to search...", key=key_a, label_visibility="collapsed")
    with cv:
        st.markdown("<div style='text-align:center;color:#334155;padding-top:8px;font-size:0.8rem;'>vs</div>", unsafe_allow_html=True)
    with c2:
        team_b = st.selectbox(f"Team B (Matchup {idx+1})", teams,
                              index=teams.index(st.session_state[key_b]) if st.session_state.get(key_b) in teams else None,
                              placeholder="Type to search...", key=key_b, label_visibility="collapsed")

    st.session_state.cmp_slots[idx] = {"a": team_a, "b": team_b}

    if not team_a or not team_b or team_a == team_b:
        return None

    ra = df[df["team"] == team_a]
    rb = df[df["team"] == team_b]
    if ra.empty or rb.empty:
        return None
    ra = ra.iloc[0]; rb = rb.iloc[0]

    games_a = nm.get_team_games(game_df, df, team_a)
    games_b = nm.get_team_games(game_df, df, team_b)

    df["_net_eff_num"] = pd.to_numeric(df["net_eff"], errors="coerce")
    df["_rank"] = df["_net_eff_num"].rank(ascending=False, method="min").astype("Int64")
    rank_a = int(df.loc[df["team"] == team_a, "_rank"].iloc[0]) if team_a in df["team"].values else None
    rank_b = int(df.loc[df["team"] == team_b, "_rank"].iloc[0]) if team_b in df["team"].values else None

    seed_a = seed_map.get(team_a)
    seed_b = seed_map.get(team_b)

    pa_base, pb_base = compute_win_prob(ra, rb, "Neutral", weights, games_a, games_b)
    adjustment, _ = compute_upset_signals(ra, rb, games_a, games_b,
                                          seed_override_a=seed_a, seed_override_b=seed_b,
                                          rank_override_a=rank_a, rank_override_b=rank_b)
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

def upset_risk_score(r):
    pa, pb = r["pa"], r["pb"]
    if pa >= pb:
        fav_net  = r.get("net_a") or 0;  dog_net  = r.get("net_b") or 0
        fav_efg  = r.get("efg_a");        dog_efg  = r.get("efg_b")
        fav_tov  = r.get("tov_a");        dog_tov  = r.get("tov_b")
        fav_orb  = r.get("orb_a");        dog_orb  = r.get("orb_b")
        fav_tmp  = r.get("tempo_a") or 68;dog_tmp  = r.get("tempo_b") or 68
        fav_sos  = r.get("sos_a");        dog_sos  = r.get("sos_b")
        fav_de   = r.get("de_a");         dog_de   = r.get("de_b")
        dog_name = r["team_b"]
    else:
        fav_net  = r.get("net_b") or 0;  dog_net  = r.get("net_a") or 0
        fav_efg  = r.get("efg_b");        dog_efg  = r.get("efg_a")
        fav_tov  = r.get("tov_b");        dog_tov  = r.get("tov_a")
        fav_orb  = r.get("orb_b");        dog_orb  = r.get("orb_a")
        fav_tmp  = r.get("tempo_b") or 68;dog_tmp  = r.get("tempo_a") or 68
        fav_sos  = r.get("sos_b");        dog_sos  = r.get("sos_a")
        fav_de   = r.get("de_b");         dog_de   = r.get("de_a")
        dog_name = r["team_a"]

    def clamp(v, lo=0.0, hi=1.0):
        return max(lo, min(hi, v))

    signals = []

    net_gap = fav_net - dog_net
    net_s = clamp(1.0 - net_gap / 20.0)
    signals.append(("Net eff gap", net_s))

    if fav_efg and dog_efg:
        efg_s = clamp((dog_efg - fav_efg + 0.05) / 0.10)
        signals.append(("eFG% edge", efg_s))

    if fav_tov and dog_tov:
        tov_s = clamp((fav_tov - dog_tov + 0.03) / 0.06)
        signals.append(("TOV% edge", tov_s))

    if fav_orb and dog_orb:
        orb_s = clamp((dog_orb - fav_orb + 0.03) / 0.06)
        signals.append(("ORB% edge", orb_s))

    tempo_diff = abs(fav_tmp - dog_tmp)
    tempo_s = clamp(tempo_diff / 10.0) * (0.6 if dog_tmp < fav_tmp else 0.3)
    signals.append(("Tempo mismatch", tempo_s))

    if fav_sos and dog_sos:
        sos_s = clamp((dog_sos - fav_sos + 0.05) / 0.15)
        signals.append(("SOS advantage", sos_s))

    if fav_de and dog_de:
        de_s = clamp((fav_de - dog_de + 3) / 8.0)
        signals.append(("Def efficiency", de_s))

    WEIGHTS = [0.30, 0.18, 0.15, 0.12, 0.10, 0.08, 0.07]
    total_w = sum(WEIGHTS[:len(signals)])
    score = sum(s * WEIGHTS[i] for i, (_, s) in enumerate(signals)) / (total_w or 1)
    pct = round(score * 100)

    if pct >= 60:   label, color = "High",   "#ef4444"
    elif pct >= 40: label, color = "Medium", "#f97316"
    elif pct >= 20: label, color = "Low",    "#fbbf24"
    else:           label, color = "Minimal","#22c55e"

    return pct, label, color, signals

def win_prob_card(result):
    pa, pb = result["pa"], result["pb"]
    ca = "#f97316" if pa >= pb else "#64748b"
    cb = "#f97316" if pb > pa  else "#64748b"
    favored = result["team_a"] if pa >= pb else result["team_b"]
    tier_label, tier_color = confidence_label(pa)

    seed_a = f' <span style="font-size:0.6rem;color:#64748b;">#{result["seed_a"]}</span>' if result.get("seed_a") else ""
    seed_b = f' <span style="font-size:0.6rem;color:#64748b;">#{result["seed_b"]}</span>' if result.get("seed_b") else ""

    return f"""
    <div style="background:#111827;border:1px solid #1e2d45;border-radius:8px;padding:1rem;margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#f1f5f9;">{result["team_a"]}{seed_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:{ca};">{pa*100:.0f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.55rem;color:#475569;">{result["record_a"]}</div>
            </div>
            <div style="text-align:center;">
                <div style="display:inline-block;padding:2px 8px;border-radius:12px;
                            background:{tier_color}22;border:1px solid {tier_color}66;
                            font-family:'DM Mono',monospace;font-size:0.55rem;
                            color:{tier_color};letter-spacing:0.05em;margin-bottom:4px;">
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

def show(season: int):
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# 📊 Matchup Comparison")

    init_state()

    df      = db.get_team_data(season)
    teams   = db.team_list(season)
    game_df = db.get_game_history(season)

    if df.empty or not teams:
        st.warning("No data yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]
    if not game_df.empty:
        game_df.columns = [c.lower() for c in game_df.columns]
        nm.build(df["team"].dropna().tolist(), game_df["team"].dropna().unique().tolist())

    seed_map = {}
    bracket_seeds_dict = {}
    try:
        import importlib, importlib.util
        _spec = importlib.util.spec_from_file_location(
            "bracket_seeds",
            os.path.join(os.path.dirname(__file__), "..", "bracket_seeds.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        bracket_seeds_dict = _mod.BRACKET_2026
        for region, seeds in _mod.BRACKET_2026.items():
            for seed, team in seeds.items():
                if team:
                    seed_map[team] = seed
    except Exception as e:
        st.warning(f"Could not load bracket seeds: {e}")

    if not seed_map:
        st.warning("Seed map is empty — check bracket_seeds.py is accessible.")

    weights = get_weights()

    seed_buttons(teams, df, seed_map, bracket_seeds_dict)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

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

    st.markdown("### Win Probabilities")
    card_cols = st.columns(len(results))
    for i, (col, r) in enumerate(zip(card_cols, results)):
        with col:
            st.markdown(win_prob_card(r), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

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

    upset_row = '<tr style="border-top:2px solid #1e2d45;border-bottom:1px solid #0f172a;background:#0d1526;">'
    upset_row += '<td style="padding:8px 12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;">Upset Risk</td>'
    for r in results:
        pct, label, color, signals = upset_risk_score(r)
        pa, pb = r["pa"], r["pb"]
        dog_name = r["team_b"] if pa >= pb else r["team_a"]
        top3 = " · ".join(f"{n}" for n, _ in signals[:3])
        badge = f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;background:{color}22;border:1px solid {color}66;color:{color};font-size:0.65rem;letter-spacing:0.05em;">{label.upper()}</span>'
        bar = f'<div style="background:#1e2d45;border-radius:3px;height:5px;margin:4px 0;overflow:hidden;"><div style="width:{pct}%;background:{color};height:100%;"></div></div>'
        upset_row += f'''<td colspan="2" style="text-align:center;padding:8px 12px;border-left:1px solid #1e2d45;">
            {badge}
            <div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;font-weight:500;color:{color};margin-top:3px;">{pct}%</div>
            {bar}
            <div style="font-size:0.58rem;color:#334155;margin-top:2px;">for {dog_name}</div>
            <div style="font-size:0.58rem;color:#475569;margin-top:2px;">{top3}</div>
        </td>'''
    upset_row += '</tr>'
    header_html += upset_row

    header_html += '</tbody></table></div>'
    st.markdown(header_html, unsafe_allow_html=True)