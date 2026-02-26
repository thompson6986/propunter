import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
import time

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V80", page_icon="🎯", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #1f6feb; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 12px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; margin-top: 15px; font-size: 1.1rem; }
    .h2h-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.9rem; }
    .score-pill { background: #010409; padding: 2px 10px; border-radius: 6px; color: #58a6ff; font-family: monospace; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- DYNAMIC ANALYSIS ENGINE ---
def analyze_match_data(fixture_id, home_team, away_team):
    # 1. Haal echte Odds op
    o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': fixture_id, 'bookmaker': 6})
    odds_data = o_res.json().get('response', [])
    
    best_market = "Geen data"
    best_odd = 0.0
    
    if odds_data:
        bets = odds_data[0]['bookmakers'][0]['bets']
        # We zoeken naar de meest logische markt (Home Win als basis, anders O/U)
        for bet in bets:
            if bet['name'] == "Match Winner":
                best_market = f"Win: {home_team}"
                best_odd = float(bet['values'][0]['odd'])
            elif bet['name'] == "Goals Over/Under" and best_odd == 0.0:
                for val in bet['values']:
                    if "1.5" in val['value']:
                        best_market = f"Totaal: {val['value']}"
                        best_odd = float(val['odd'])
    
    return best_market, best_odd

# --- UI ---
if 'analysis_cache' not in st.session_state: st.session_state.analysis_cache = []

t1, t2, t3 = st.tabs(["🚀 DASHBOARD", "📊 DEEP ANALYSIS", "🏟️ STADIUM"])

with t2:
    st.header("📊 Deep Market Analysis")
    if st.button("🔍 START ANALYSE (LIVE ODDS)", use_container_width=True):
        with st.spinner("Real-time odds en H2H vergelijken..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 8})
            fixtures = res.json().get('response', [])
            temp_cache = []
            
            for f in fixtures:
                f_id = f['fixture']['id']
                h_name = f['teams']['home']['name']
                a_name = f['teams']['away']['name']
                
                # Echte H2H
                h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{f['teams']['home']['id']}-{f['teams']['away']['id']}"})
                h2h_list = h2h_res.json().get('response', [])[:3]
                
                # Echte Odds & Markt Analyse
                m_name, m_odd = analyze_match_data(f_id, h_name, a_name)
                
                temp_cache.append({
                    'f': f, 'h2h': h2h_list, 'market': m_name, 'odd': m_odd
                })
            st.session_state.analysis_cache = temp_cache

    # RENDER ANALYSE
    for item in st.session_state.analysis_cache:
        f = item['f']
        st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
        st.markdown(f"### {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
        
        # H2H Sectie
        if item['h2h']:
            st.markdown("<b>Historische Resultaten:</b>", unsafe_allow_html=True)
            for h in item['h2h']:
                hg = h['goals']['home'] if h['goals']['home'] is not None else "-"
                ag = h['goals']['away'] if h['goals']['away'] is not None else "-"
                st.markdown(f'''<div class="h2h-row">
                    <span>{h['teams']['home']['name']} - {h['teams']['away']['name']}</span>
                    <span class="score-pill">{hg} - {ag}</span>
                </div>''', unsafe_allow_html=True)
        
        # De Berekende Tip (DYNAMIC)
        st.markdown(f'''<div class="safe-pick">🛡️ LIVE TIP: {item['market']} (@{item['odd']})</div>''', unsafe_allow_html=True)
        
        if st.button(f"Bevestig Bet @{item['odd']}", key=f"bet_v80_{f['fixture']['id']}"):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": item['odd'], "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": item['market'], "odd": item['odd'], "fixture_id": f['fixture']['id']}],
                    "stake": 10.0
                })
                st.success(f"Bet geplaatst: {item['market']} @{item['odd']}")
        st.markdown('</div>', unsafe_allow_html=True)

# [Tab 1 & 3 blijven stabiel]
