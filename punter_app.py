import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter V91", page_icon="📝", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border-left: 5px solid #1f6feb; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #30363d; }
    .builder-row { display: flex; justify-content: space-between; background: #0d1117; padding: 10px; border-radius: 8px; margin-bottom: 5px; border: 1px solid #30363d; }
    .add-btn { background-color: #238636 !important; color: white !important; width: 100%; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- DB & SESSION STATE ---
if 'my_selections' not in st.session_state: st.session_state.my_selections = []
if 'euro_cache' not in st.session_state: st.session_state.euro_cache = []

def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- APP TABS ---
t1, t2, t3 = st.tabs(["🚀 BETSLIP BUILDER", "📊 DEEP ANALYSIS", "📈 TRACKER"])

# --- TAB 2: ANALYSE (HERSTELD & ADDER) ---
with t2:
    st.header("📊 Analyseer Europese Matches")
    if st.button("🔍 SCAN TOP MATCHES VANAVOND", use_container_width=True):
        with st.spinner("Data ophalen uit API..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
            all_fix = res.json().get('response', [])
            # Filter op Europa League (3) en Conference (848)
            st.session_state.euro_cache = [f for f in all_fix if f['league']['id'] in [3, 848]]
            st.rerun()

    if st.session_state.euro_cache:
        for f in st.session_state.euro_cache[:10]:
            f_id = f['fixture']['id']
            h, a = f['teams']['home']['name'], f['teams']['away']['name']
            start = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
            
            # Statische markt-logica voor nu (Odds-fetch kan hieronder)
            suggested_odd = 1.65 
            market = "Win or Draw (1X)"

            st.markdown(f'''
                <div class="analysis-card">
                    <div style="display:flex; justify-content:space-between;">
                        <b>{h} vs {a}</b>
                        <span style="color:#8b949e;">🕒 {start}</span>
                    </div>
                    <div style="color:#3fb950; margin-top:5px;">🛡️ Tip: {market} (@{suggested_odd})</div>
                </div>
            ''', unsafe_allow_html=True)
            
            if st.button(f"➕ Voeg toe: {h}", key=f"add_{f_id}"):
                st.session_state.my_selections.append({
                    "match": f"{h} vs {a}", 
                    "market": market, 
                    "odd": suggested_odd,
                    "start_time": start,
                    "league": f['league']['name']
                })
                st.toast(f"Toegevoegd: {h} vs {a}")

# --- TAB 1: BUILDER (SYNC MET ANALYSE) ---
with t1:
    st.header("📝 Jouw Selecties")
    if not st.session_state.my_selections:
        st.info("De builder is leeg. Ga naar 'Deep Analysis' en klik op de groene '+' knoppen.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.markdown(f'''<div class="builder-row">
                <div><b>{sel['match']}</b><br><small>{sel['market']} (@{sel['odd']})</small></div>
            </div>''', unsafe_allow_html=True)
        
        st.success(f"Totaal Gecombineerde Odd: **@{total_odd:.2f}**")
        if st.button("🔥 BEVESTIG DEZE BETSLIP", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01",
                    "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2),
                    "matches": st.session_state.my_selections,
                    "stake": 10.0,
                    "start_time": st.session_state.my_selections[0]['start_time']
                })
                st.session_state.my_selections = []
                st.balloons()
                st.rerun()

# --- TAB 3: TRACKER ---
with t3:
    st.header("📈 Bankroll Tracker")
    # Hier komen de bevestigde bets uit de database...
