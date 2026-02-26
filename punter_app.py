import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V84", page_icon="🏦", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- BOOKMAKER LIJST ---
# 6: Bwin, 1: 10Bet, 2: Bet365, 3: 188Bet, 4: Pinnacle, 7: Bet-at-home, 8: Unibet
BOOKMAKERS = {
    "Bwin": 6,
    "Bet365": 2,
    "Unibet": 8,
    "Pinnacle": 4,
    "10Bet": 1,
    "Bet-at-home": 7
}

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .bookmaker-panel { background: #1c2128; border: 1px solid #30363d; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-top: 3px solid #f1e05a; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 12px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
if not firebase_admin._apps and "firebase" in st.secrets:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)
db = firestore.client() if firebase_admin._apps else None

# --- UI ---
t1, t2, t3 = st.tabs(["🚀 DASHBOARD", "📊 BOOKMAKER ANALYSIS", "🏟️ STADIUM"])

with t2:
    st.markdown('<div class="bookmaker-panel">', unsafe_allow_html=True)
    st.subheader("🏦 Bookmaker Selectie")
    selected_bm_name = st.selectbox("Kies je favoriete bookmaker voor de analyse:", list(BOOKMAKERS.keys()))
    selected_bm_id = BOOKMAKERS[selected_bm_name]
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button(f"🔍 ANALYSEER MET {selected_bm_name} ODDS", use_container_width=True):
        with st.spinner(f"Bezig met ophalen van {selected_bm_name} data..."):
            # Focus op top Europese leagues vanavond
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 10})
            fixtures = res.json().get('response', [])
            
            st.session_state.bm_cache = []
            for f in fixtures:
                f_id = f['fixture']['id']
                # Odds specifiek voor de GEKOZEN bookmaker
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': selected_bm_id})
                o_data = o_res.json().get('response', [])
                
                final_odd = 0.0
                final_market = "Geen Odds Beschikbaar"
                
                if o_data and len(o_data) > 0:
                    # De API geeft hier enkel de odds van de gekozen bookmaker terug
                    for bet in o_data[0]['bookmakers'][0]['bets']:
                        if bet['name'] == "Match Winner":
                            final_market = f"Win: {f['teams']['home']['name']}"
                            final_odd = float(bet['values'][0]['odd'])
                            break
                
                st.session_state.bm_cache.append({
                    'f': f, 'market': final_market, 'odd': final_odd, 'bm_name': selected_bm_name
                })

    # Render Resultaten
    if 'bm_cache' in st.session_state:
        for item in st.session_state.bm_cache:
            f = item['f']
            st.markdown(f'<div class="analysis-card">', unsafe_allow_html=True)
            st.markdown(f"### {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            st.caption(f"Competitie: {f['league']['name']} | Bron: {item['bm_name']}")
            
            if item['odd'] > 0:
                st.markdown(f'''<div class="safe-pick">🛡️ {item['bm_name']} TIP: {item['market']} (@{item['odd']})</div>''', unsafe_allow_html=True)
                if st.button(f"Plaats @{item['odd']}", key=f"bm_bet_{f['fixture']['id']}"):
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                            "total_odd": item['odd'], "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": item['market'], "odd": item['odd']}],
                            "stake": 10.0, "bookmaker": item['bm_name']
                        })
                        st.toast(f"Bet geplaatst via {item['bm_name']}!")
            else:
                st.warning(f"⚠️ {item['bm_name']} heeft momenteel geen odds voor deze match.")
            st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f'<div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div><script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>', height=1000)
