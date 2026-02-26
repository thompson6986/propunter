import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Suite V54", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

# --- API & DB SETUP ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# ... (Firebase init code blijft hetzelfde) ...

# --- TABS ---
t1, t2 = st.tabs(["🚀 SLIP GENERATOR", "📡 LIVE TRACKER"])

with t1:
    st.markdown(f"### 🚀 Generator | 💰 Saldo: **€{st.session_state.get('balance', 100):.2f}**")
    
    with st.container():
        st.markdown('<div style="background-color: #161b22; padding: 20px; border-radius: 12px;">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        target_odd_cat = c1.selectbox("Doel Odds per Slip", [1.5, 2.0, 3.0, 5.0]) # Jouw gevraagde odds
        m_count = c2.slider("Matchen per Slip", 1, 5, 2)
        window = c3.selectbox("Tijdvenster", ["6 uur", "Vandaag"])
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER NIEUWE VARIATIE", use_container_width=True):
        try:
            with st.spinner("Zoeken naar specifieke odds..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                data = res.json()
                
                if data.get('response'):
                    now_ts = int(time.time())
                    limit_h = 6 if window == "6 uur" else 24
                    
                    pool = []
                    # We pakken een grotere steekproef om variatie te garanderen
                    fixtures = data['response'][:40] 
                    
                    for f in fixtures:
                        ts = f['fixture']['timestamp']
                        if 0.01 <= (ts - now_ts)/3600 <= limit_h:
                            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f['fixture']['id']})
                            o_data = o_res.json()
                            if o_data.get('response'):
                                for bm in o_data['response'][0]['bookmakers']:
                                    for bet in bm['bets']:
                                        if bet['name'] in ["Match Winner", "Double Chance", "Goals Over/Under"]:
                                            for val in bet['values']:
                                                odd = float(val['odd'])
                                                # We zoeken bets die gezamenlijk de 'target_odd_cat' benaderen
                                                if 1.20 <= odd <= 3.00: 
                                                    pool.append({
                                                        "fixture_id": f['fixture']['id'], 
                                                        "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                        "market": f"{bet['name']}: {val['value']}", 
                                                        "odd": odd, 
                                                        "prob": round((1/odd)*100+4, 1),
                                                        "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')
                                                    })
                    
                    # Logica om slips te bouwen die dicht bij de target odd liggen
                    random.shuffle(pool)
                    new_slips = []
                    for _ in range(5): # Maak 5 verschillende slips
                        current_slip = random.sample(pool, min(m_count, len(pool)))
                        current_total = 1.0
                        for m in current_slip: current_total *= m['odd']
                        
                        # Alleen slips tonen die in de buurt van de gevraagde odd liggen
                        if (target_odd_cat * 0.7) <= current_total <= (target_odd_cat * 1.5):
                            new_slips.append(current_slip)
                    
                    st.session_state.gen_slips = new_slips
        except: st.error("Fout bij ophalen. Probeer opnieuw.")

    # ... (Display code blijft hetzelfde als V53) ...
