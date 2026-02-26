import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Dashboard", page_icon="⚽", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

# --- DATABASE FIX & VERBINDING ---
if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Live Tracker & Cash-out"])

# [Tab 1: Generator blijft gelijk aan V41]

with t2:
    st.title("📡 Live Portfolio Tracker")
    user_id = st.text_input("Bevestig User ID", value="punter_01")
    
    if db:
        try:
            # FORCEER DE EXACTE QUERY DIE BIJ JE INDEX PAST
            # Sorteer op timestamp DESCENDING (nieuwste eerst)
            saved_ref = db.collection("saved_slips")
            query = saved_ref.where("user_id", "==", user_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(15)
            saved = query.get()

            if not saved:
                st.info("Geen actieve slips gevonden voor dit ID.")
            else:
                # 1. Haal alle live data op
                f_ids = []
                docs_data = []
                for doc in saved:
                    d = doc.to_dict()
                    d['id'] = doc.id
                    docs_data.append(d)
                    for m in d['matches']: f_ids.append(m['fixture_id'])
                
                live_updates = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []):
                            live_updates[f['fixture']['id']] = f

                # 2. Toon Slips met Cash-out logica
                for s in docs_data:
                    with st.container():
                        st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                        col_info, col_cash = st.columns([3, 1])
                        
                        total_progress = 0
                        match_count = len(s['matches'])
                        
                        with col_info:
                            st.subheader(f"Slip @{s['total_odd']}")
                            for m in s['matches']:
                                f_id = m['fixture_id']
                                f_data = live_updates.get(f_id)
                                score_str = "Nog niet gestart"
                                status_icon = "⚪"
                                
                                if f_data:
                                    h_g = f_data['goals']['home']
                                    a_g = f_data['goals']['away']
                                    status = f_data['fixture']['status']['short']
                                    score_str = f"{h_g} - {a_g}"
                                    
                                    if status in ['1H', '2H', 'HT']:
                                        status_icon = "🔴"
                                        # Simpele progress check voor cash-out
                                        total_progress += 0.5 
                                    elif status == 'FT':
                                        status_icon = "🏁"
                                        total_progress += 1.0

                                st.write(f"{status_icon} **{m['match']}**: {score_str} ({m['market']})")

                        with col_cash:
                            # BASIS CASH-OUT BEREKENING (Indicatief)
                            # Gebaseerd op hoeveel wedstrijden er al 'goed' staan
                            inzet = 10 # Voorbeeld inzet
                            potentiële_winst = inzet * s['total_odd']
                            
                            # Cashout factor: hoe dichter bij FT, hoe hoger het bedrag
                            cashout_val = round((potentiële_winst * (total_progress / match_count)) * 0.8, 2)
                            
                            st.markdown(f"### 💰 Cash-out")
                            if total_progress > 0:
                                st.button(f"€ {max(cashout_val, 1.0)}", key=f"co_{s['id']}")
                            else:
                                st.caption("Beschikbaar na aftrap")

                        if st.button("🗑️ Verwijder Slip", key=f"del_{s['id']}"):
                            db.collection("saved_slips").document(s['id']).delete()
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Fout bij ophalen: {e}")
            st.info("Als Firebase 'Enabled' zegt, herstart dan je Streamlit app (R in de console) om de verbinding te verversen.")
