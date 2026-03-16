import streamlit as st

st.set_page_config(
    page_title="NCAAB Madness",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
    --court:  #0a0f1e;
    --paint:  #111827;
    --line:   #1e2d45;
    --orange: #f97316;
    --amber:  #fbbf24;
    --muted:  #64748b;
    --text:   #f1f5f9;
    --good:   #22c55e;
    --bad:    #ef4444;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--court) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stSidebar"] {
    background-color: var(--paint) !important;
    border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebarNav"] { display: none !important; }

h1,h2,h3 {
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 0.05em !important;
    color: var(--text) !important;
}
.stButton > button {
    background: var(--orange) !important;
    color: #000 !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 1rem !important;
    letter-spacing: 0.08em !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover { background: var(--amber) !important; transform: translateY(-1px) !important; }

[data-testid="stMetricValue"] {
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 2rem !important;
    color: var(--orange) !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.7rem !important;
    color: var(--muted) !important;
    text-transform: uppercase !important;
}
.stSelectbox label, .stMultiSelect label, .stSlider label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.75rem !important;
    color: var(--muted) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}
.stat-card {
    background: var(--paint);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
}
.matchup-banner {
    background: linear-gradient(135deg, var(--paint) 0%, #0f172a 100%);
    border: 1px solid var(--line);
    border-top: 3px solid var(--orange);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    margin-bottom: 1.5rem;
}
.tag {
    display: inline-block;
    background: var(--line);
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.tag.orange { background: rgba(249,115,22,0.15); color: var(--orange); }
.tag.green  { background: rgba(34,197,94,0.15);  color: var(--good); }
.tag.red    { background: rgba(239,68,68,0.15);   color: var(--bad); }
hr { border-color: var(--line) !important; }
section.main, .block-container { background-color: var(--court) !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 1.5rem 0;">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#f97316;line-height:1;">
            NCAAB<br><span style="color:#f1f5f9;">MADNESS</span>
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:0.65rem;color:#64748b;
                    letter-spacing:0.1em;text-transform:uppercase;margin-top:4px;">
            2025–26 Analytics Tool
        </div>
    </div>
    <hr style="margin-bottom:1rem;">
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        ["🏀  Overview", "📊  Team Explorer", "⚔️  Matchup Simulator", "📋  Compare Matchups", "🏆  Bracket", "📈  Game Log", "🔄  Data Status"],
        label_visibility="collapsed"
    )

if   "Overview"  in page: from pages import overview;         overview.show()
elif "Explorer"  in page: from pages import explorer;         explorer.show()
elif "Matchup"   in page: from pages import matchup;          matchup.show()
elif "Compare"   in page: from pages import matchup_compare;  matchup_compare.show()
elif "Game Log"  in page: from pages import gamelog;          gamelog.show()
elif "Bracket"   in page: from pages import bracket;          bracket.show()
elif "Status"    in page: from pages import status;           status.show()