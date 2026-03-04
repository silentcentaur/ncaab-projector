"""
Matchup Simulator — Customizable Win Probability Model
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

# ── Model ─────────────────────────────────────────────────────────────────────

def logistic(x):
    return 1 / (1 + np.exp(-x))

def recent_form_score(game_df: pd.DataFrame, team: str, n: int = 10) -> float:
    """
    Returns a form score between -1 and 1 based on last N games.
    Weighted so more recent games count more.
    """
    if game_df.empty or "team" not in game_df.columns:
        return 0.0
    tg = game_df[game_df["team"] == team].copy()
    if tg.empty:
        return 0.0
    tg["date"] = pd.to_datetime(tg["date"], errors="coerce")
    tg = tg.sort_values("date", ascending=False).head(n)
    if tg.empty:
        return 0.0
    weights = np.array([1 / (i + 1) for i in range(len(tg))])  # 1, 1/2, 1/3...
    results = np.array([1.0 if r == "W" else -1.0 for r in tg["result"].fillna("L")])
    return float(np.dot(weights, results) / weights.sum())

def avg_margin(game_df: pd.DataFrame, team: str, n: int = 10) -> float:
    if game_df.empty or "team" not in game_df.columns:
        return 0.0
    tg = game_df[game_df["team"] == team].copy()
    if tg.empty:
        return 0.0
    tg["date"]   = pd.to_datetime(tg["date"], errors="coerce")
    tg["margin"] = pd.to_numeric(tg["margin"], errors="coerce")
    tg = tg.sort_values("date", ascending=False).head(n)
    return float(tg["margin"].mean()) if not tg["margin"].isna().all() else 0.0

def compute_win_prob(ra, rb, venue, weights, game_df):
    """
    Weighted linear model:
      score = w_oe*(OE diff) + w_de*(DE diff) + w_efg*(eFG diff)
            + w_tov*(TOV diff, inverted) + w_orb*(ORB diff)
            + w_sos*(SOS diff) + w_form*(form diff) + w_margin*(margin diff)
            + hca
    → logistic(score * scale) = win probability
    """
    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    # Raw diffs (positive = team A advantage)
    oe_diff     = g(ra,"adj_oe",100)    - g(rb,"adj_oe",100)
    de_diff     = g(rb,"adj_de",100)    - g(ra,"adj_de",100)   # lower DE is better, so flip
    efg_diff    = g(ra,"efg_pct")       - g(rb,"efg_pct")
    tov_diff    = g(rb,"tov_pct")       - g(ra,"tov_pct")      # lower TOV is better, flip
    orb_diff    = g(ra,"orb_pct")       - g(rb,"orb_pct")
    sos_diff    = g(ra,"sos_oe")        - g(rb,"sos_oe")

    # Recent form
    form_a      = recent_form_score(game_df, ra["team"])
    form_b      = recent_form_score(game_df, rb["team"])
    form_diff   = form_a - form_b

    # Recent margin
    margin_a    = avg_margin(game_df, ra["team"])
    margin_b    = avg_margin(game_df, rb["team"])
    margin_diff = margin_a - margin_b

    # Home court
    hca = {"Home": 3.5, "Neutral": 0.0, "Away": -3.5}[venue]

    # Weighted score
    # Scale factors normalize each component to similar magnitudes
    score = (
        weights["oe"]     * oe_diff     * 0.15 +
        weights["de"]     * de_diff     * 0.15 +
        weights["efg"]    * efg_diff    * 8.0  +   # eFG is 0-1 scale
        weights["tov"]    * tov_diff    * 8.0  +
        weights["orb"]    * orb_diff    * 5.0  +
        weights["sos"]    * sos_diff    * 0.05 +
        weights["form"]   * form_diff   * 1.5  +
        weights["margin"] * margin_diff * 0.08 +
        hca * 0.15
    )

    prob = logistic(score)
    return round(prob, 4), round(1 - prob, 4)

def expected_score(oe, de, opp_oe, opp_de, tempo, opp_tempo):
    t = (tempo + opp_tempo) / 2
    return round(((oe + opp_de) / 2) / 100 * t, 1), round(((opp_oe + de) / 2) / 100 * t, 1)

# ── UI Helpers ────────────────────────────────────────────────────────────────

def stat_bar(label, va, vb, higher_is_better=True, fmt=".2f"):
    if va is None or vb is None or pd.isna(va) or pd.isna(vb): return
    total = abs(va) + abs(vb)
    if total == 0: return
    tp = abs(va) / total * 100
    better = (va > vb) if higher_is_better else (va < vb)
    tc = "#f97316" if better else "#64748b"
    oc = "#f97316" if not better else "#64748b"
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

# ── Default weights ───────────────────────────────────────────────────────────

DEFAULTS = {
    "oe":     1.0,
    "de":     1.0,
    "efg":    0.8,
    "tov":    0.6,
    "orb":    0.5,
    "sos":    0.4,
    "form":   0.6,
    "margin": 0.4,
}

# ── Page ──────────────────────────────────────────────────────────────────────

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)

    st.markdown("# ⚔️ Matchup Simulator")

    df      = db.get_team_data()
    teams   = db.team_list()
    game_df = db.get_game_history()

    if df.empty or not teams:
        st.warning("No data in database yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]

    # ── Team pickers ──────────────────────────────────────────────────────────
    c1, cv, c2 = st.columns([5, 1, 5])
    with c1: team_a = st.selectbox("Team A", teams, index=None, placeholder="Type to search...")
    with cv: st.markdown("<div style='text-align:center;font-size:1.8rem;color:#64748b;padding-top:1.8rem;'>VS</div>", unsafe_allow_html=True)
    with c2: team_b = st.selectbox("Team B", teams, index=None, placeholder="Type to search...")

    venue = st.select_slider("Venue (from Team A's perspective)",
                             options=["Away", "Neutral", "Home"], value="Neutral")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Model weights ─────────────────────────────────────────────────────────
    with st.expander("⚙️  Customize Prediction Model", expanded=False):
        st.markdown("""
        <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;
                    text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;">
            Adjust how much each factor influences the win probability.
            0 = ignore completely · 1 = default · 2 = double weight
        </div>""", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Efficiency**")
            w_oe  = st.slider("Adj. Offensive Efficiency", 0.0, 2.0, DEFAULTS["oe"],  0.1, key="w_oe")
            w_de  = st.slider("Adj. Defensive Efficiency", 0.0, 2.0, DEFAULTS["de"],  0.1, key="w_de")
            w_sos = st.slider("Strength of Schedule",      0.0, 2.0, DEFAULTS["sos"], 0.1, key="w_sos")
            w_margin = st.slider("Recent Point Margin",    0.0, 2.0, DEFAULTS["margin"], 0.1, key="w_margin")
        with col2:
            st.markdown("**Four Factors**")
            w_efg  = st.slider("Effective FG%",      0.0, 2.0, DEFAULTS["efg"],  0.1, key="w_efg")
            w_tov  = st.slider("Turnover Rate",       0.0, 2.0, DEFAULTS["tov"],  0.1, key="w_tov")
            w_orb  = st.slider("Off. Rebound Rate",   0.0, 2.0, DEFAULTS["orb"],  0.1, key="w_orb")
            w_form = st.slider("Recent Form (W/L)",   0.0, 2.0, DEFAULTS["form"], 0.1, key="w_form")

        if st.button("Reset to Defaults"):
            for key, val in DEFAULTS.items():
                st.session_state[f"w_{key}"] = val
            st.rerun()

        # Show active weight summary
        active = {k: v for k, v in {
            "Off. Eff": w_oe, "Def. Eff": w_de, "eFG%": w_efg,
            "TOV%": w_tov, "ORB%": w_orb, "SOS": w_sos,
            "Form": w_form, "Margin": w_margin
        }.items() if v > 0}
        total_w = sum(active.values())
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;margin-bottom:6px;">Active factor weights</div>', unsafe_allow_html=True)
        bar_html = '<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;width:100%;">'
        factor_colors = ["#f97316","#fbbf24","#22c55e","#06b6d4","#a78bfa","#f43f5e","#84cc16","#fb923c"]
        for i, (label, w) in enumerate(active.items()):
            pct = w / total_w * 100
            bar_html += f'<div style="width:{pct:.1f}%;background:{factor_colors[i%len(factor_colors)]};"></div>'
        bar_html += '</div>'
        legend_html = '<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:6px;">'
        for i, (label, w) in enumerate(active.items()):
            legend_html += f'<span style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:{factor_colors[i%len(factor_colors)]};">{label} {w:.1f}</span>'
        legend_html += '</div>'
        st.markdown(bar_html + legend_html, unsafe_allow_html=True)

    weights = {"oe": w_oe, "de": w_de, "efg": w_efg, "tov": w_tov,
               "orb": w_orb, "sos": w_sos, "form": w_form, "margin": w_margin}

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

    pa, pb = compute_win_prob(ra, rb, venue, weights, game_df)

    # ── Win probability banner ────────────────────────────────────────────────
    st.markdown(f"""
    <div class="matchup-banner">
        <div style="display:flex;justify-content:space-around;align-items:center;">
            <div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;">{team_a}</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#f97316;">{pa*100:.1f}%</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#64748b;">WIN PROBABILITY</div>
            </div>
            <div style="font-size:1.2rem;color:#334155;">VS</div>
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
                <span>{team_a}</span>
                <span>{venue}</span>
                <span>{team_b}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Projected score ───────────────────────────────────────────────────────
    oe_a=float(ra.get("adj_oe") or 100); de_a=float(ra.get("adj_de") or 100)
    oe_b=float(rb.get("adj_oe") or 100); de_b=float(rb.get("adj_de") or 100)
    t_a =float(ra.get("adj_tempo") or 68); t_b=float(rb.get("adj_tempo") or 68)
    s_a, s_b = expected_score(oe_a, de_a, oe_b, de_b, t_a, t_b)

    sc1, sc2, sc3 = st.columns([3, 1, 3])
    sc1.metric(f"{team_a} Proj. Score", s_a)
    sc2.markdown("<div style='text-align:center;padding-top:1.5rem;color:#64748b;'>–</div>", unsafe_allow_html=True)
    sc3.metric(f"{team_b} Proj. Score", s_b)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Factor breakdown ──────────────────────────────────────────────────────
    st.markdown("### Factor Breakdown")
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;margin-bottom:1rem;">How each active factor favors each team</div>', unsafe_allow_html=True)

    def g(row, col, default=0.0):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    form_a   = recent_form_score(game_df, team_a)
    form_b   = recent_form_score(game_df, team_b)
    margin_a = avg_margin(game_df, team_a)
    margin_b = avg_margin(game_df, team_b)

    factors = [
        ("Adj. Offensive Eff.", g(ra,"adj_oe",100),  g(rb,"adj_oe",100),  True,  ".1f", w_oe),
        ("Adj. Defensive Eff.", g(ra,"adj_de",100),  g(rb,"adj_de",100),  False, ".1f", w_de),
        ("Effective FG%",       g(ra,"efg_pct"),      g(rb,"efg_pct"),      True,  ".3f", w_efg),
        ("Turnover Rate",       g(ra,"tov_pct"),      g(rb,"tov_pct"),      False, ".3f", w_tov),
        ("Off. Rebound Rate",   g(ra,"orb_pct"),      g(rb,"orb_pct"),      True,  ".3f", w_orb),
        ("Strength of Schedule",g(ra,"sos_oe"),       g(rb,"sos_oe"),       True,  ".3f", w_sos),
        ("Recent Form",         form_a,               form_b,               True,  ".2f", w_form),
        ("Recent Avg Margin",   margin_a,             margin_b,             True,  ".1f", w_margin),
    ]

    for label, va, vb, hib, fmt, w in factors:
        if w > 0:
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:#334155;text-transform:uppercase;margin-top:0.5rem;">weight: {w:.1f}</div>', unsafe_allow_html=True)
            stat_bar(label, va, vb, hib, fmt)

    # ── Recent form ───────────────────────────────────────────────────────────
    if not game_df.empty and "team" in game_df.columns:
        st.markdown("### Recent Form (Last 10 Games)")
        fc1, fc2 = st.columns(2)
        for col_w, tname in [(fc1, team_a), (fc2, team_b)]:
            tg = game_df[game_df["team"] == tname].copy()
            if not tg.empty and "result" in tg.columns:
                tg["date"] = pd.to_datetime(tg["date"], errors="coerce")
                tg = tg.sort_values("date", ascending=False).head(10)
                w  = (tg["result"] == "W").sum()
                l  = (tg["result"] == "L").sum()
                col_w.markdown(f"**{tname}**: {w}W – {l}L")
                col_w.markdown("".join([
                    f'<span class="tag {"green" if r=="W" else "red"}" style="margin:2px;">{r}</span>'
                    for r in tg["result"].tolist()
                ]), unsafe_allow_html=True)