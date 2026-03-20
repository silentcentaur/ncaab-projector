import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db
import name_map as nm
import bracket_seeds as bs

def logistic(x): return 1 / (1 + np.exp(-x))

def recent_form_score(games: pd.DataFrame, n: int = 10) -> float:
    if games.empty: return 0.0
    games = games.copy()
    games["date"] = pd.to_datetime(games["date"], errors="coerce")
    games = games.sort_values("date", ascending=False).head(n)
    if games.empty: return 0.0
    weights = np.array([1 / (i + 1) for i in range(len(games))])
    results = np.array([1.0 if r == "W" else -1.0 for r in games["result"].fillna("L")])
    return float(np.dot(weights, results) / weights.sum())

def avg_margin(games: pd.DataFrame, n: int = 10) -> float:
    if games.empty: return 0.0
    games = games.copy()
    games["date"]   = pd.to_datetime(games["date"], errors="coerce")
    games["margin"] = pd.to_numeric(games["margin"], errors="coerce")
    games = games.sort_values("date", ascending=False).head(n)
    return float(games["margin"].mean()) if not games["margin"].isna().all() else 0.0

def compute_win_prob(ra, rb, venue, weights, games_a, games_b):
    def g(row, col):
        v = row.get(col)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def diff(va, vb, flip=False):
        if va is None or vb is None: return None
        if va == 0.0 and vb == 0.0: return None
        return (vb - va) if flip else (va - vb)

    oe_a = g(ra,"adj_oe"); oe_b = g(rb,"adj_oe")
    de_a = g(ra,"adj_de"); de_b = g(rb,"adj_de")

    oe_diff     = (oe_a - oe_b)   if oe_a and oe_b else 0.0
    de_diff     = (de_b - de_a)   if de_a and de_b else 0.0
    efg_diff    = diff(g(ra,"efg_pct"), g(rb,"efg_pct"))
    tov_diff    = diff(g(ra,"tov_pct"), g(rb,"tov_pct"), flip=True)
    orb_diff    = diff(g(ra,"orb_pct"), g(rb,"orb_pct"))
    sos_diff    = diff(g(ra,"sos_oe"),  g(rb,"sos_oe"))
    form_diff   = recent_form_score(games_a) - recent_form_score(games_b)
    margin_diff = avg_margin(games_a)        - avg_margin(games_b)
    hca         = {"Home":3.5,"Neutral":0.0,"Away":-3.5}[venue]

    score = (
        weights["oe"]     * oe_diff                          * 0.15 +
        weights["de"]     * de_diff                          * 0.15 +
        weights["efg"]    * (efg_diff or 0.0)                * 8.0  +
        weights["tov"]    * (tov_diff or 0.0)                * 8.0  +
        weights["orb"]    * (orb_diff or 0.0)                * 5.0  +
        weights["sos"]    * (sos_diff or 0.0)                * 0.05 +
        weights["form"]   * form_diff                        * 1.5  +
        weights["margin"] * margin_diff                      * 0.08 +
        hca * 0.15
    )
    prob = logistic(score)
    return round(prob, 4), round(1 - prob, 4)

def expected_score(oe, de, opp_oe, opp_de, tempo, opp_tempo):
    t = (tempo + opp_tempo) / 2
    return round(((oe + opp_de) / 2) / 100 * t, 1), round(((opp_oe + de) / 2) / 100 * t, 1)

def stat_bar(label, va, vb, higher_is_better=True, fmt=".2f"):
    if va is None or vb is None:
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#334155;margin-bottom:0.75rem;">{label}: no data available</div>', unsafe_allow_html=True)
        return
    if pd.isna(va) or pd.isna(vb): return
    if va == 0.0 and vb == 0.0:
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#334155;margin-bottom:0.75rem;">{label}: no data available</div>', unsafe_allow_html=True)
        return
    total = abs(va) + abs(vb)
    if total == 0: return
    tp     = abs(va) / total * 100
    better = (va > vb) if higher_is_better else (va < vb)
    tc     = "#f97316" if better else "#64748b"
    oc     = "#f97316" if not better else "#64748b"
    st.markdown(f"""
    <div style="margin-bottom:0.75rem;">
        <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                    font-size:0.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">
            <span style="color:{tc};">{va:{fmt}}</span>
            <span>{label}</span>
            <span style="color:{oc};">{vb:{fmt}}</span>
        </div>
        <div style="background:#1e2d45;border-radius:4px;height:10px;overflow:hidden;display:flex;">
            <div style="width:{tp:.1f}%;background:{tc};"></div>
            <div style="flex:1;background:{oc};"></div>
        </div>
    </div>""", unsafe_allow_html=True)

DEFAULTS = {"oe":1.0,"de":1.0,"efg":0.8,"tov":0.6,"orb":0.5,"sos":0.4,"form":0.6,"margin":0.4}

SEED_TO_EXPECTED_RANK  = {1:4, 2:11, 3:18, 4:25, 5:33, 6:41, 7:49, 8:57,
                           9:63,10:69,11:74,12:80,13:88,14:96,15:108,16:120}
SEED_TO_EXPECTED_DE    = {1:88, 2:90, 3:92, 4:94, 5:96, 6:97, 7:98, 8:99,
                           9:100,10:101,11:102,12:103,13:104,14:106,15:108,16:110}
SEED_TO_EXPECTED_EM    = {1:28, 2:22, 3:18, 4:14, 5:11, 6:9,  7:7,  8:5,
                           9:4,  10:3, 11:2, 12:1, 13:0, 14:-2,15:-4,16:-6}
SEED_TO_EXPECTED_SOS   = {1:.24,2:.22,3:.20,4:.18,5:.16,6:.14,7:.12,8:.10,
                           9:.09,10:.08,11:.07,12:.06,13:.05,14:.04,15:.03,16:.02}
AVG_TEMPO = 68.0

SIGNAL_META = {
    "rank_gap":    {"label": "Seed vs T-Rank gap",                "weight": 0.30},
    "def_edge":    {"label": "Defense vs seed expectation",       "weight": 0.20},
    "em_mismatch": {"label": "Efficiency margin vs seed",         "weight": 0.20},
    "tempo":       {"label": "Tempo mismatch (underdog benefit)", "weight": 0.15},
    "form":        {"label": "Recent form vs seed expectation",   "weight": 0.10},
    "sos":         {"label": "Schedule strength vs seed",         "weight": 0.05},
}

def _safe(row, col, default=None):
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)): return default
    try: return float(v)
    except (TypeError, ValueError): return default

def _seed_relative(value, expected_for_seed, scale, invert=False):
    if value is None or expected_for_seed is None: return 0.0
    diff = expected_for_seed - value if invert else value - expected_for_seed
    return diff / scale

def compute_upset_signals(ra, rb, games_a, games_b, seed_override_a=None, seed_override_b=None,
                          rank_override_a=None, rank_override_b=None):
    seed_a  = _safe(ra, "seed") or seed_override_a
    seed_b  = _safe(rb, "seed") or seed_override_b
    trank_a = _safe(ra, "barthag_rk") or _safe(ra, "trank") or _safe(ra, "rk") or rank_override_a
    trank_b = _safe(rb, "barthag_rk") or _safe(rb, "trank") or _safe(rb, "rk") or rank_override_b
    adj_oe_a = _safe(ra, "adj_oe", 100); adj_oe_b = _safe(rb, "adj_oe", 100)
    adj_de_a = _safe(ra, "adj_de", 100); adj_de_b = _safe(rb, "adj_de", 100)
    tempo_a  = _safe(ra, "adj_tempo", AVG_TEMPO)
    tempo_b  = _safe(rb, "adj_tempo", AVG_TEMPO)
    sos_a    = _safe(ra, "sos_oe");      sos_b    = _safe(rb, "sos_oe")
    form_a   = recent_form_score(games_a)
    form_b   = recent_form_score(games_b)
    em_a     = adj_oe_a - adj_de_a
    em_b     = adj_oe_b - adj_de_b

    has_seeds = seed_a is not None and seed_b is not None
    sa, sb    = (int(seed_a) if has_seeds else None), (int(seed_b) if has_seeds else None)

    raw = {}

    if has_seeds and trank_a and trank_b:
        exp_rank_a = SEED_TO_EXPECTED_RANK.get(sa, sa * 7)
        exp_rank_b = SEED_TO_EXPECTED_RANK.get(sb, sb * 7)
        score_a = _seed_relative(trank_a, exp_rank_a, scale=12, invert=True)
        score_b = _seed_relative(trank_b, exp_rank_b, scale=12, invert=True)
        raw["rank_gap"] = score_a - score_b
    elif trank_a and trank_b:
        raw["rank_gap"] = (trank_b - trank_a) / 60.0
    else:
        raw["rank_gap"] = 0.0

    if has_seeds:
        exp_de_a = SEED_TO_EXPECTED_DE.get(sa, 100)
        exp_de_b = SEED_TO_EXPECTED_DE.get(sb, 100)
        score_a = _seed_relative(adj_de_a, exp_de_a, scale=4, invert=True)
        score_b = _seed_relative(adj_de_b, exp_de_b, scale=4, invert=True)
        raw["def_edge"] = score_a - score_b
    else:
        raw["def_edge"] = (adj_de_b - adj_de_a) / 4.0

    if has_seeds:
        exp_em_a = SEED_TO_EXPECTED_EM.get(sa, 0)
        exp_em_b = SEED_TO_EXPECTED_EM.get(sb, 0)
        score_a = _seed_relative(em_a, exp_em_a, scale=5)
        score_b = _seed_relative(em_b, exp_em_b, scale=5)
        raw["em_mismatch"] = score_a - score_b
    else:
        raw["em_mismatch"] = (em_a - em_b) / 8.0

    if has_seeds:
        underdog_seed  = max(sa, sb)
        underdog_tempo = tempo_a if sa == underdog_seed else tempo_b
        favorite_tempo = tempo_b if sa == underdog_seed else tempo_a
        tempo_diff     = favorite_tempo - underdog_tempo
        sign = 1 if sa == underdog_seed else -1
        raw["tempo"] = sign * (tempo_diff / 6.0)
    else:
        if trank_a and trank_b:
            underdog_is_a  = trank_a > trank_b
            tempo_diff     = tempo_b - tempo_a if underdog_is_a else tempo_a - tempo_b
            sign           = 1 if underdog_is_a else -1
            raw["tempo"]   = sign * (tempo_diff / 6.0)
        else:
            raw["tempo"] = 0.0

    if has_seeds:
        seed_weight_a = min(1.0 + (sa - 1) / 30.0, 1.5)
        seed_weight_b = min(1.0 + (sb - 1) / 30.0, 1.5)
        raw["form"] = (form_a * seed_weight_a) - (form_b * seed_weight_b)
    else:
        raw["form"] = (form_a - form_b)

    if has_seeds and sos_a is not None and sos_b is not None:
        exp_sos_a = SEED_TO_EXPECTED_SOS.get(sa, 0.10)
        exp_sos_b = SEED_TO_EXPECTED_SOS.get(sb, 0.10)
        score_a = _seed_relative(sos_a, exp_sos_a, scale=0.08)
        score_b = _seed_relative(sos_b, exp_sos_b, scale=0.08)
        raw["sos"] = score_a - score_b
    elif sos_a is not None and sos_b is not None:
        raw["sos"] = (sos_a - sos_b) / 0.08
    else:
        raw["sos"] = 0.0

    composite = sum(
        SIGNAL_META[k]["weight"] * float(np.clip(raw[k], -3, 3))
        for k in SIGNAL_META
    )
    adjustment = float(np.clip(composite * 0.06, -0.12, 0.12))

    signals = []
    for k, meta in SIGNAL_META.items():
        val     = raw[k]
        clamped = float(np.clip(val, -3, 3))
        contrib = meta["weight"] * clamped
        signals.append({
            "key":    k,
            "label":  meta["label"],
            "weight": meta["weight"],
            "raw":    val,
            "score":  clamped,
            "contrib": contrib,
            "favors": "a" if contrib > 0.01 else ("b" if contrib < -0.01 else "neutral"),
            "no_seed": not has_seeds,
        })

    return adjustment, signals


def confidence_label(pa):
    p = max(pa, 1 - pa)
    if p < 0.55:   return "Toss-up",         "#a78bfa"
    if p < 0.65:   return "Lean",             "#06b6d4"
    if p < 0.75:   return "Moderate favorite","#f97316"
    if p < 0.85:   return "Strong favorite",  "#f97316"
    return             "Heavy favorite",      "#ef4444"


def render_signal_breakdown(team_a, team_b, pa_base, pb_base, pa_adj, pb_adj, adjustment, signals,
                            seed_a=None, region_a=None, seed_b=None, region_b=None):
    direction = "▲" if adjustment > 0 else ("▼" if adjustment < 0 else "–")
    favored   = team_a if adjustment > 0 else (team_b if adjustment < 0 else "Neither")
    adj_pp    = abs(adjustment) * 100

    seed_str_a = f"#{seed_a} {region_a}" if seed_a else "not seeded"
    seed_str_b = f"#{seed_b} {region_b}" if seed_b else "not seeded"

    with st.expander(f"🔬  Upset Signal Analysis  ·  {direction} {adj_pp:.1f}pp adjustment ({favored})", expanded=False):
        no_seed = any(s.get("no_seed") for s in signals)
        seed_note = " · <span style='color:#f97316;'>no seeds set — using T-Rank relative mode</span>" if no_seed else ""
        st.markdown(
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;'
            f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">'
            f'Base probability adjusted from {pa_base*100:.1f}% → {pa_adj*100:.1f}% for {team_a}{seed_note}</div>'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:#334155;margin-bottom:1rem;">'
            f'<span style="color:#f97316;">{team_a}</span> {seed_str_a} &nbsp;·&nbsp; '
            f'<span style="color:#06b6d4;">{team_b}</span> {seed_str_b}</div>',
            unsafe_allow_html=True
        )

        for s in signals:
            bar_pct  = min(abs(s["score"]) / 3.0 * 100, 100)
            color    = "#f97316" if s["favors"] == "a" else ("#06b6d4" if s["favors"] == "b" else "#334155")
            favors_label = team_a if s["favors"] == "a" else (team_b if s["favors"] == "b" else "Even")
            contrib_str  = f"+{s['contrib']:.3f}" if s["contrib"] >= 0 else f"{s['contrib']:.3f}"
            st.markdown(f"""
            <div style="margin-bottom:1rem;">
                <div style="display:flex;justify-content:space-between;
                            font-family:'DM Mono',monospace;font-size:0.65rem;
                            color:#94a3b8;margin-bottom:4px;">
                    <span>{s['label']}</span>
                    <span style="color:{color};">{favors_label} &nbsp;{contrib_str}</span>
                </div>
                <div style="background:#1e2d45;border-radius:4px;height:7px;overflow:hidden;">
                    <div style="width:{bar_pct:.1f}%;background:{color};height:100%;
                                {'margin-left:auto;' if s['favors']=='b' else ''}"></div>
                </div>
                <div style="font-family:'DM Mono',monospace;font-size:0.58rem;
                            color:#334155;margin-top:2px;">weight {s['weight']:.2f}</div>
            </div>""", unsafe_allow_html=True)

        total_pos = sum(s["contrib"] for s in signals if s["contrib"] > 0)
        total_neg = abs(sum(s["contrib"] for s in signals if s["contrib"] < 0))
        total     = total_pos + total_neg or 1
        st.markdown(f"""
        <div style="margin-top:1.5rem;border-top:1px solid #1e2d45;padding-top:1rem;">
            <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:#64748b;
                        text-transform:uppercase;margin-bottom:6px;">composite signal balance</div>
            <div style="background:#1e2d45;border-radius:4px;height:10px;overflow:hidden;display:flex;">
                <div style="width:{total_pos/total*100:.1f}%;background:#f97316;"></div>
                <div style="flex:1;background:#06b6d4;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                        font-size:0.6rem;color:#64748b;margin-top:4px;">
                <span style="color:#f97316;">{team_a}</span>
                <span style="color:#06b6d4;">{team_b}</span>
            </div>
        </div>""", unsafe_allow_html=True)

def show(season: int):
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# ⚔️ Matchup Simulator")

    df      = db.get_team_data(season)
    teams   = db.team_list(season)
    game_df = db.get_game_history(season)

    if df.empty or not teams:
        st.warning("No data in database yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]

    if not game_df.empty:
        game_df.columns = [c.lower() for c in game_df.columns]
        nm.build(df["team"].dropna().tolist(),
                 game_df["team"].dropna().unique().tolist())

    c1, cv, c2 = st.columns([5,1,5])
    with c1: team_a = st.selectbox("Team A", teams, index=None, placeholder="Type to search...")
    with cv: st.markdown("<div style='text-align:center;font-size:1.8rem;color:#64748b;padding-top:1.8rem;'>VS</div>", unsafe_allow_html=True)
    with c2: team_b = st.selectbox("Team B", teams, index=None, placeholder="Type to search...")
    venue = st.select_slider("Venue (from Team A's perspective)",
                             options=["Away","Neutral","Home"], value="Neutral")

    st.markdown("<br>", unsafe_allow_html=True)

    for k, v in DEFAULTS.items():
        if f"w_{k}" not in st.session_state:
            st.session_state[f"w_{k}"] = v

    with st.expander("⚙️  Customize Prediction Model", expanded=False):
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;">0 = ignore · 1 = default · 2 = double weight</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Efficiency**")
            w_oe     = st.slider("Adj. Offensive Efficiency", 0.0, 2.0, DEFAULTS["oe"],     0.1, key="w_oe")
            w_de     = st.slider("Adj. Defensive Efficiency", 0.0, 2.0, DEFAULTS["de"],     0.1, key="w_de")
            w_sos    = st.slider("Strength of Schedule",      0.0, 2.0, DEFAULTS["sos"],    0.1, key="w_sos")
            w_margin = st.slider("Recent Point Margin",       0.0, 2.0, DEFAULTS["margin"], 0.1, key="w_margin")
        with col2:
            st.markdown("**Four Factors**")
            w_efg  = st.slider("Effective FG%",    0.0, 2.0, DEFAULTS["efg"],  0.1, key="w_efg")
            w_tov  = st.slider("Turnover Rate",    0.0, 2.0, DEFAULTS["tov"],  0.1, key="w_tov")
            w_orb  = st.slider("Off. Rebound Rate",0.0, 2.0, DEFAULTS["orb"],  0.1, key="w_orb")
            w_form = st.slider("Recent Form (W/L)",0.0, 2.0, DEFAULTS["form"], 0.1, key="w_form")
        if st.button("Reset to Defaults"):
            for k, v in DEFAULTS.items():
                st.session_state[f"w_{k}"] = v
            st.rerun()

        active = {k:v for k,v in {"Off.Eff":w_oe,"Def.Eff":w_de,"eFG%":w_efg,
                                   "TOV%":w_tov,"ORB%":w_orb,"SOS":w_sos,
                                   "Form":w_form,"Margin":w_margin}.items() if v>0}
        total_w = sum(active.values()) or 1
        colors  = ["#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa","#f43f5e","#84cc16","#fb923c"]
        bar_html = '<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;width:100%;margin-top:1rem;">'
        for i,(lbl,w) in enumerate(active.items()):
            bar_html += f'<div style="width:{w/total_w*100:.1f}%;background:{colors[i%len(colors)]};"></div>'
        bar_html += '</div><div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:6px;">'
        for i,(lbl,w) in enumerate(active.items()):
            bar_html += f'<span style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:{colors[i%len(colors)]};">{lbl} {w:.1f}</span>'
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

    weights = {"oe":w_oe,"de":w_de,"efg":w_efg,"tov":w_tov,
               "orb":w_orb,"sos":w_sos,"form":w_form,"margin":w_margin}

    if not team_a or not team_b:
        st.markdown("""
        <div style="margin-top:2rem;text-align:center;padding:3rem;border:1px dashed #1e2d45;border-radius:8px;">
            <div style="font-size:2rem;color:#334155;font-weight:700;">SELECT TWO TEAMS TO BEGIN</div>
            <div style="font-size:0.8rem;color:#334155;margin-top:0.5rem;">Type a team name in either box above</div>
        </div>""", unsafe_allow_html=True)
        return
    if team_a == team_b:
        st.warning("Select two different teams.")
        return

    ra = df[df["team"] == team_a].iloc[0]
    rb = df[df["team"] == team_b].iloc[0]

    df["_net_eff_num"] = pd.to_numeric(df["net_eff"], errors="coerce")
    df["_rank"] = df["_net_eff_num"].rank(ascending=False, method="min").astype("Int64")
    rank_a = int(df.loc[df["team"] == team_a, "_rank"].iloc[0]) if team_a in df["team"].values else None
    rank_b = int(df.loc[df["team"] == team_b, "_rank"].iloc[0]) if team_b in df["team"].values else None

    games_a = nm.get_team_games(game_df, df, team_a)
    games_b = nm.get_team_games(game_df, df, team_b)

    pa_base, pb_base = compute_win_prob(ra, rb, venue, weights, games_a, games_b)

    seed_a, region_a = bs.get_seed(team_a)
    seed_b, region_b = bs.get_seed(team_b)
    adjustment, signals = compute_upset_signals(ra, rb, games_a, games_b,
                                                seed_override_a=seed_a,
                                                seed_override_b=seed_b,
                                                rank_override_a=rank_a,
                                                rank_override_b=rank_b)
    pa = round(float(np.clip(pa_base + adjustment, 0.05, 0.95)), 4)
    pb = round(1 - pa, 4)

    tier_label, tier_color = confidence_label(pa)
    st.markdown(f"""
    <div class="matchup-banner">
        <div style="display:flex;justify-content:space-around;align-items:center;">
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;">{team_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#f97316;">{pa*100:.1f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;">WIN PROBABILITY</div>
            </div>
            <div style="text-align:center;">
                <div style="display:inline-block;padding:4px 12px;border-radius:20px;
                            background:{tier_color}22;border:1px solid {tier_color}66;
                            font-family:'DM Mono',monospace;font-size:0.65rem;
                            color:{tier_color};letter-spacing:0.08em;margin-bottom:8px;">
                    {tier_label.upper()}
                </div>
                <div style="font-size:1.2rem;color:#334155;">VS</div>
            </div>
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;">{team_b}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#64748b;">{pb*100:.1f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;">WIN PROBABILITY</div>
            </div>
        </div>
        <div style="margin-top:1.5rem;">
            <div style="background:#1e2d45;border-radius:6px;height:20px;overflow:hidden;display:flex;">
                <div style="width:{pa*100:.1f}%;background:#f97316;"></div>
                <div style="flex:1;background:#334155;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                        font-size:0.65rem;color:#64748b;margin-top:4px;">
                <span>{team_a}</span><span>{venue}</span><span>{team_b}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    render_signal_breakdown(team_a, team_b, pa_base, pb_base, pa, pb, adjustment, signals,
                            seed_a=seed_a, region_a=region_a,
                            seed_b=seed_b, region_b=region_b)

    oe_a=float(ra.get("adj_oe") or 100); de_a=float(ra.get("adj_de") or 100)
    oe_b=float(rb.get("adj_oe") or 100); de_b=float(rb.get("adj_de") or 100)
    t_a =float(ra.get("adj_tempo") or 68); t_b=float(rb.get("adj_tempo") or 68)
    s_a, s_b = expected_score(oe_a, de_a, oe_b, de_b, t_a, t_b)
    sc1,sc2,sc3 = st.columns([3,1,3])
    sc1.metric(f"{team_a} Proj. Score", s_a)
    sc2.markdown("<div style='text-align:center;padding-top:1.5rem;color:#64748b;'>–</div>", unsafe_allow_html=True)
    sc3.metric(f"{team_b} Proj. Score", s_b)

    st.markdown("<br>", unsafe_allow_html=True)

    import plotly.graph_objects as go

    def get_percentile(val, all_vals, higher_is_better=True):
        if val is None or pd.isna(val): return None
        arr = [v for v in all_vals if v is not None and not pd.isna(v)]
        if not arr: return None
        pct = sum(v <= val for v in arr) / len(arr) * 100
        return pct if higher_is_better else 100 - pct

    df2 = db.get_team_data(season)
    if not df2.empty:
        df2.columns = [c.lower() for c in df2.columns]
        def col_vals(col):
            return pd.to_numeric(df2[col], errors="coerce").dropna().tolist() if col in df2.columns else []

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
        labels = [m[0] for m in radar_metrics]

        def team_percentiles(row):
            vals = []
            for label, col, hib in radar_metrics:
                v = row.get(col)
                v = float(v) if v is not None and not pd.isna(v) else None
                pct = get_percentile(v, col_vals(col), hib)
                vals.append(pct if pct is not None else 0)
            return vals

        pcts_a = team_percentiles(ra)
        pcts_b = team_percentiles(rb)
        labels_closed = labels + [labels[0]]
        pcts_a_closed = pcts_a + [pcts_a[0]]
        pcts_b_closed = pcts_b + [pcts_b[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=pcts_a_closed, theta=labels_closed,
            fill="toself", name=team_a,
            line=dict(color="#f97316", width=2),
            fillcolor="rgba(249,115,22,0.15)"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=pcts_b_closed, theta=labels_closed,
            fill="toself", name=team_b,
            line=dict(color="#06b6d4", width=2),
            fillcolor="rgba(6,182,212,0.15)"
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0,100],
                                tickfont=dict(size=8, color="#475569"),
                                gridcolor="#1e2d45",
                                tickvals=[25,50,75,100],
                                ticktext=["25%","50%","75%","100%"]),
                angularaxis=dict(tickfont=dict(size=11, color="#94a3b8"), gridcolor="#1e2d45"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f1f5f9", family="DM Sans"),
            legend=dict(font=dict(size=11, color="#94a3b8"),
                        bgcolor="rgba(0,0,0,0)", x=0.5, y=-0.1,
                        orientation="h", xanchor="center"),
            margin=dict(l=60, r=60, t=40, b=60),
            title=dict(text="SEASON PROFILE VS. NATIONAL PERCENTILES",
                       font=dict(family="Bebas Neue", size=16, color="#f1f5f9"),
                       x=0, xanchor="left"),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### Factor Breakdown")
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;margin-bottom:1rem;">How each active factor favors each team</div>', unsafe_allow_html=True)

    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    form_a   = recent_form_score(games_a)
    form_b   = recent_form_score(games_b)
    margin_a = avg_margin(games_a)
    margin_b = avg_margin(games_b)

    factors = [
        ("Adj. Offensive Eff.", g(ra,"adj_oe",100), g(rb,"adj_oe",100), True,  ".1f", w_oe),
        ("Adj. Defensive Eff.", g(ra,"adj_de",100), g(rb,"adj_de",100), False, ".1f", w_de),
        ("Effective FG%",       g(ra,"efg_pct"),     g(rb,"efg_pct"),    True,  ".3f", w_efg),
        ("Turnover Rate",       g(ra,"tov_pct"),     g(rb,"tov_pct"),    False, ".3f", w_tov),
        ("Off. Rebound Rate",   g(ra,"orb_pct"),     g(rb,"orb_pct"),    True,  ".3f", w_orb),
        ("Strength of Schedule",g(ra,"sos_oe"),      g(rb,"sos_oe"),     True,  ".3f", w_sos),
        ("Recent Form",         form_a,              form_b,             True,  ".2f", w_form),
        ("Recent Avg Margin",   margin_a,            margin_b,           True,  ".1f", w_margin),
    ]
    for label, va, vb, hib, fmt, w in factors:
        if w > 0:
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:#334155;text-transform:uppercase;margin-top:0.5rem;">weight: {w:.1f}</div>', unsafe_allow_html=True)
            stat_bar(label, va, vb, hib, fmt)

    st.markdown("### Recent Form (Last 10 Games)")
    fc1, fc2 = st.columns(2)
    for col_w, tname, tgames in [(fc1, team_a, games_a), (fc2, team_b, games_b)]:
        if not tgames.empty and "result" in tgames.columns:
            tg = tgames.copy()
            tg["date"] = pd.to_datetime(tg["date"], errors="coerce")
            tg = tg.sort_values("date", ascending=False).head(10)
            w  = (tg["result"] == "W").sum()
            l  = (tg["result"] == "L").sum()
            col_w.markdown(f"**{tname}**: {w}W – {l}L")
            col_w.markdown("".join([
                f'<span class="tag {"green" if r=="W" else "red"}" style="margin:2px;">{r}</span>'
                for r in tg["result"].tolist()
            ]), unsafe_allow_html=True)
        else:
            col_w.markdown(f"**{tname}**: No game data")