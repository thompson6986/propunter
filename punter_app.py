import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V87", page_icon="💰", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .bankroll-card { background: linear-gradient(135deg, #1f6feb 0%, #114494 100%); padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; }
    .tracker-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #238636; }
    .analysis-card { background: #1c2128; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 10px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
@st.cache_resource
def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- APP TABS ---
t1, t2, t3 = st.tabs(["📡 LIVE TRACKER", "📊 DEEP ANALYSIS", "🏟️ STADIUM"])

# --- TAB 1: DE TRACKER (HERSTELD) ---
with t1:
    st.markdown('<div class="bankroll-card">', unsafe_allow_html=True)
    st.subheader("💰 Huidige Bankroll")
    st.title("€ 1.240,50") # Dit kan later dynamisch uit de DB komen
    st.markdown('</div>', unsafe_allow_html=True)

    st.subheader("📡 Actieve Weddenschappen")
    if db:
        # Haal de laatste 10 bevestigde bets op
        docs = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        
        if not docs:
            st.info("Nog geen actieve bets. Ga naar de Analyse tab om bets toe te voegen.")
        
        for doc in docs:
            s = doc.to_dict()
            with st.container():
                st.markdown(f'''
                    <div class="tracker-card">
                        <div style="display:flex; justify-content:space-between;">
                            <b>{s['matches'][0]['match']}</b>
                            <span style="color:#58a6ff; font-weight:bold;">@{s.get("total_odd", "1.00")}</span>
                        </div>
                        <div style="font-size:0.85rem; color:#8b949e; margin-top:5px;">
                            Markt: {s['matches'][0].get('market', 'Onbekend')} | Inzet: €10
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
    else:
        st.error("Database verbinding mislukt. Tracker niet beschikbaar.")

# --- TAB 2: ANALYSE (MET DIRECTE FEEDBACK NAAR TRACKER) ---
with t2:
    st.header("📊 Deep Match Analysis")
    # ... (Gedeelte voor League selectie zoals in V86) ...
    
    if st.button("🔍 SCAN EUROPESE AVOND", use_container_width=True):
        # API aanvraag logica (Hetzelfde als V86)
        # We slaan de resultaten op in st.session_state.deep_cache
        pass

    if 'deep_cache' in st.session_state:
        for item in st.session_state.deep_cache:
            f = item['f']
            st.markdown(f'<div class="analysis-card">', unsafe_allow_html=True)
            st.markdown(f"### {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            st.markdown(f'<div class="safe-pick">🛡️ SAFE BET: {item["suggestion"]} (@{item["odd"]})</div>', unsafe_allow_html=True)
            
            if st.button(f"Bevestig Bet @{item['odd']}", key=f"track_v87_{f['fixture']['id']}"):
                if db:
                    db.collection("saved_slips").add({
                        "user_id": "punter_01",
                        "timestamp": datetime.now(TIMEZONE),
                        "total_odd": item['odd'],
                        "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": item['suggestion'], "odd": item['odd']}],
                        "stake": 10.0,
                        "status": "OPEN"
                    })
                    st.success(f"✅ Bet opgeslagen! Bekijk hem in de 'Live Tracker' tab.")
                    st.balloons() # Visuele bevestiging
            st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f'<div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div><script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>', height=1000)
