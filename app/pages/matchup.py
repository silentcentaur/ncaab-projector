import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

def logistic(x): return 1 / (1 + np.exp(-x))

def win_probability(net_a, net_b, venue):
    hca  = {"Home":3.5,"Neutral":0.0,"Away":-3.5}[venue]
    prob = logistic(((net_a - net_b) + hca) * 0.15)
    return round(prob,4), round(1-prob,4)

def expected_score(oe,de,opp_oe,opp_de,tempo,opp_tempo):
    t = (tempo+opp_tempo)/2
    return round(((oe+opp_de)/2)/100*t,1), round(((opp_oe+de)/2)/100*t,1)

def stat_bar(label, va, vb, higher_is_better=True):
    if va is None or vb is None or pd.isna(va) or pd.isna(vb): return
    total = va + vb
    if total == 0: return
    tp = va/total*100
    better = (va>vb) if higher_is_better else (va<vb)
    tc = "#f97316" if better else "#64748b"
    oc = "#f97316" if not better else "#64748b"
    st.markdown(f"""
    <div style="margin-bottom:0.75rem;">
        <div style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;
                    font-size:0.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">
            <span style="color:{tc};">{va:.2f}</span><span>{label}</span><span style="color:{oc};">{vb:.2f}</span>
        </div>
        <div style="background:#1e2d45;border-radius:4px;height:10px;overflow:hidden;display:flex;">
            <div style="width:{tp:.1f}%;background:{tc};"></div>
            <div style="flex:1;background:{oc};"></div>
        </div>
    </div>""", unsafe_allow_html=True)

def show():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"],section.main,.block-container{background-color:#0a0f1e!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("# ⚔️ Matchup Simulator")

    df    = db.get_team_data()
    teams = db.team_list()
    if df.empty or not teams:
        st.warning("No data in database yet. Run the pipeline first.")
        return
    df.columns = [c.lower() for c in df.columns]

    c1, cv, c2 = st.columns([5,1,5])
    with c1: team_a = st.selectbox("Team A", teams, index=None, placeholder="Type to search...")
    with cv: st.markdown("<div style='text-align:center;font-size:1.8rem;color:#64748b;padding-top:1.8rem;'>VS</div>", unsafe_allow_html=True)
    with c2: team_b = st.selectbox("Team B", teams, index=None, placeholder="Type to search...")

    venue = st.select_slider("Venue (from Team A's perspective)",
                             options=["Away","Neutral","Home"], value="Neutral")

    if not team_a or not team_b:
        st.markdown("""
        <div style="margin-top:4rem;text-align:center;padding:3rem;border:1px dashed #1e2d45;border-radius:8px;">
            <div style="font-size:2rem;color:#334155;font-weight:700;">SELECT TWO TEAMS TO BEGIN</div>
            <div style="font-size:0.8rem;color:#334155;margin-top:0.5rem;">Type a team name in either box above</div>
        </div>""", unsafe_allow_html=True)
        return

    if team_a == team_b:
        st.warning("Select two different teams.")
        return

    ra = df[df["team"]==team_a].iloc[0]
    rb = df[df["team"]==team_b].iloc[0]

    net_a  = float(ra.get("net_eff") or 0)
    net_b  = float(rb.get("net_eff") or 0)
    pa, pb = win_probability(net_a, net_b, venue)

    st.markdown("<br>", unsafe_allow_html=True)
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
                <span>{venue} · Net Eff Δ {net_a-net_b:+.1f}</span>
                <span>{team_b}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    oe_a=float(ra.get("adj_oe") or 100); de_a=float(ra.get("adj_de") or 100)
    oe_b=float(rb.get("adj_oe") or 100); de_b=float(rb.get("adj_de") or 100)
    t_a =float(ra.get("adj_tempo") or 68); t_b=float(rb.get("adj_tempo") or 68)
    s_a, s_b = expected_score(oe_a,de_a,oe_b,de_b,t_a,t_b)

    sc1,sc2,sc3 = st.columns([3,1,3])
    sc1.metric(f"{team_a} Proj. Score", s_a)
    sc2.markdown("<div style='text-align:center;padding-top:1.5rem;color:#64748b;'>–</div>", unsafe_allow_html=True)
    sc3.metric(f"{team_b} Proj. Score", s_b)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Stat Comparison")
    cl,cr = st.columns(2)
    cl.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.1rem;color:#f97316;">{team_a}</div>', unsafe_allow_html=True)
    cr.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.1rem;color:#64748b;text-align:right;">{team_b}</div>', unsafe_allow_html=True)

    for label,col,hib in [
        ("Adj. Offensive Eff.","adj_oe",True), ("Adj. Defensive Eff.","adj_de",False),
        ("Tempo","adj_tempo",True), ("eFG%","efg_pct",True), ("Opp eFG%","opp_efg_pct",False),
        ("TOV%","tov_pct",False), ("ORB%","orb_pct",True), ("FTR","ftr",True),
        ("Net Efficiency","net_eff",True),
    ]:
        va,vb = ra.get(col), rb.get(col)
        if va is not None and vb is not None and not pd.isna(va) and not pd.isna(vb):
            stat_bar(label, float(va), float(vb), hib)

    gdf = db.get_game_history()
    if not gdf.empty and "team" in gdf.columns:
        st.markdown("### Recent Form (Last 10 Games)")
        fc1,fc2 = st.columns(2)
        for col_w, tname in [(fc1,team_a),(fc2,team_b)]:
            tg = gdf[gdf["team"]==tname].tail(10)
            if not tg.empty and "result" in tg.columns:
                w=(tg["result"]=="W").sum(); l=(tg["result"]=="L").sum()
                col_w.markdown(f"**{tname}**: {w}W – {l}L")
                col_w.markdown("".join([
                    f'<span class="tag {"green" if r=="W" else "red"}" style="margin:2px;">{r}</span>'
                    for r in tg["result"].tolist()
                ]), unsafe_allow_html=True)
