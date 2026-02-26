import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter V92", page_icon="📝", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border-left: 5px solid #1f6feb; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #30363d; }
    .builder-row { display: flex; justify-content: space-between; background: #1c2128; padding: 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #30363d; }
    .total-odd-box { background: #23863622; border: 1px solid #238636; padding: 15px; border-radius: 10px; text-align: center; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE & DB ---
if 'my_selections' not in st.session_state: st.session_state.my_selections = []
if 'euro_cache' not in st.session_state: st.session_state.euro_cache = []

@st.cache_resource
def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 BETSLIP BUILDER", "📊 DEEP ANALYSIS", "📈 TRACKER"])

# --- TAB 2: ANALYSE (MET DATA-CHECK) ---
with t2:
    st.header("📊 Analyseer Europese Matches")
    if st.button("🔍 SCAN TOP MATCHES VANAVOND", use_container_width=True):
        with st.spinner("Data ophalen uit API..."):
            try:
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
                data = res.json()
                # VEILIGHEIDS-CHECK: Bestaat 'response' en is het een lijst?
                if data.get('response') and isinstance(data['response'], list):
                    # Filter op Europa League (3) en Conference (848)
                    st.session_state.euro_cache = [f for f in data['response'] if f.get('league') and f['league']['id'] in [3, 848]]
                    if not st.session_state.euro_cache:
                        st.warning("Geen Europese matchen gevonden voor deze selectie.")
                else:
                    st.error("API gaf geen geldige respons. Controleer je credits.")
            except Exception as e:
                st.error(f"Verbindingsfout: {e}")

    if st.session_state.euro_cache:
        for f in st.session_state.euro_cache[:10]:
            # Gebruik .get() om KeyErrors te voorkomen
            fixture = f.get('fixture', {})
            teams = f.get('teams', {})
            f_id = fixture.get('id')
            h, a = teams.get('home', {}).get('name', 'Team A'), teams.get('away', {}).get('name', 'Team B')
            
            if f_id:
                start = datetime.fromtimestamp(fixture.get('timestamp', 0), TIMEZONE).strftime('%H:%M')
                market = "Win or Draw (1X)"
                odd = 1.45 # Dit kan nog dynamisch via de odds-call
                
                st.markdown(f'''
                    <div class="analysis-card">
                        <div style="display:flex; justify-content:space-between;">
                            <b>{h} vs {a}</b>
                            <span style="color:#8b949e;">🕒 {start}</span>
                        </div>
                        <div style="color:#3fb950; margin-top:5px; font-weight:bold;">🛡️ Veiligste Keuze: {market} (@{odd})</div>
                    </div>
                ''', unsafe_allow_html=True)
                
                if st.button(f"➕ Voeg {h} toe aan slip", key=f"btn_{f_id}"):
                    st.session_state.my_selections.append({
                        "match": f"{h} vs {a}", "market": market, "odd": odd, "start_time": start
                    })
                    st.toast(f"Toegevoegd: {h}")

# --- TAB 1: BUILDER ---
with t1:
    st.header("📝 Jouw Eigen Betslip")
    if not st.session_state.my_selections:
        st.info("Ga naar 'Deep Analysis' om wedstrijden toe te voegen met de '+' knop.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.markdown(f'''<div class="builder-row">
                <span><b>{sel['match']}</b><br><small>{sel['market']}</small></span>
                <span style="color:#58a6ff; font-weight:bold;">@{sel['odd']}</span>
            </div>''', unsafe_allow_html=True)
        
        st.markdown(f'''<div class="total-odd-box">
            Totaal Gecombineerde Odd: <b style="font-size:1.5rem;">@{total_odd:.2f}</b><br>
            <small>Potentiële winst bij €10: €{total_odd * 10:.2f}</small>
        </div>''', unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Wis Alles", use_container_width=True):
            st.session_state.my_selections = []; st.rerun()
        if c2.button("🔥 BEVESTIG BETSLIP", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2), "matches": st.session_state.my_selections,
                    "stake": 10.0, "start_time": st.session_state.my_selections[0]['start_time']
                })
                st.session_state.my_selections = []
                st.success("Opgeslagen in Tracker!")
                st.balloons()
