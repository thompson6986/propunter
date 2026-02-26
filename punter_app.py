import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime, timedelta
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter V74", page_icon="⚙️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .control-panel { background-color: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; margin-bottom: 25px; }
    .slip-card { border: 1px solid #30363d; padding: 15px; border-radius: 12px; margin-bottom: 15px; background: #0d1117; border-left: 5px solid #238636; }
    .match-info { font-size: 1.1rem; font-weight: bold; color: #f0f6fc; }
    .market-info { color: #8b949e; font-size: 0.9rem; margin-top: 4px; }
    </style>
    """, unsafe_allow_html=True)

# --- API & DB SETUP ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- TABS ---
t1, t2, t3 = st.tabs(["⚙️ GENERATOR", "📡 TRACKER", "🏟️ STADIUM"])

with t1:
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    st.subheader("🛠️ Handmatige Markt Scan")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # We zetten deze standaard op 24 uur om alles te pakken
        lookahead = st.slider("Tijdvenster (volgende X uur)", 1, 48, 24)
        min_prob = st.slider("Min. Slaagkans (%)", 10, 95, 45)
    with col2:
        min_o = st.number_input("Min. Odds", 1.10, 5.0, 1.25)
        max_o = st.number_input("Max. Odds", 1.10, 15.0, 5.0)
    with col3:
        sel_markets = st.multiselect("Markten", ["Match Winner", "Both Teams Score", "Goals Over/Under"], ["Match Winner", "Both Teams Score"])
        u_id = st.text_input("User ID", value="punter_01")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 START DEEP SCAN", use_container_width=True):
        try:
            with st.spinner("Bezig met ophalen van alle aankomende topwedstrijden..."):
                now = datetime.now(TIMEZONE)
                limit_dt = now + timedelta(hours=lookahead)
                
                # FIX: We halen 'next 50' op ipv te filteren op datum/status. Dit pakt ALLES wat nu komt.
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 50})
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response']:
                        f_dt = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE)
                        
                        # Alleen wedstrijden in jouw gekozen tijdvenster
                        if now <= f_dt <= limit_dt:
                            f_id = f['fixture']['id']
                            
                            # Odds call
                            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
                            o_data = o_res.json()
                            
                            if o_data.get('response'):
                                for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                                    if bet['name'] in sel_markets:
                                        for val in bet['values']:
                                            odd_val = float(val['odd'])
                                            prob_val = (1 / odd_val) * 100
                                            
                                            # Jouw professionele filters toepassen
                                            if min_o <= odd_val <= max_o and prob_val >= min_prob:
                                                if any(x in str(val['value']) for x in ["Asian", "Corner", "3.5", "4.5"]): continue
                                                pool.append({
                                                    "fixture_id": f_id,
                                                    "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                                    "market": f"{bet['name']}: {val['value']}",
                                                    "odd": odd_val,
                                                    "prob": round(prob_val, 1),
                                                    "start_time": f_dt.strftime('%H:%M')
                                                })
                    
                    st.session_state.found_matches = pool
                    if not pool:
                        st.info("ℹ️ Geen resultaten binnen deze odds/kans-range. Probeer de filters iets ruimer te zetten.")
                else:
                    st.error("API gaf geen respons. Controleer je credits.")
        except: st.error("Fout in de scan-engine.")

    if st.session_state.get('found_matches'):
        st.markdown(f"### ✅ {len(st.session_state.found_matches)} Opties Gevonden")
        for i, m in enumerate(st.session_state.found_matches):
            st.markdown(f'''
                <div class="slip-card">
                    <div class="match-info">🕒 {m['start_time']} | {m['match']}</div>
                    <div class="market-info">Weddenschap: {m['market']} (@{m['odd']})</div>
                    <div style="color:#238636; font-size:0.85rem; font-weight:bold;">Statistische kans: {m['prob']}%</div>
                </div>
            ''', unsafe_allow_html=True)
            if st.button(f"Zet €10 op {m['match']} @{m['odd']}", key=f"bet_{i}"):
                if db:
                    db.collection("saved_slips").add({
                        "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                        "total_odd": m['odd'], "matches": [m], "stake": 10.0
                    })
                    st.toast("Toegevoegd aan tracker!")

# [Tracker & Stadium blijven gelijk]
