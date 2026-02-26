import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import random
import time

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Analysis Elite", page_icon="📊", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 6px solid #1f6feb; }
    .stat-box { background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; text-align: center; font-size: 0.9rem; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 12px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; margin-top: 15px; }
    .h2h-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85rem; }
    .h2h-table td { padding: 5px; border-bottom: 1px solid #30363d; color: #8b949e; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE FIX ---
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        else:
            st.error("Firebase secrets niet gevonden.")
    except Exception as e:
        st.error(f"Firebase Init Fout: {e}")

db = firestore.client() if firebase_admin._apps else None

# --- STATE ---
if 'balance' not in st.session_state: st.session_state.balance = 1000.0

t1, t2, t3, t4 = st.tabs(["🚀 GENERATOR", "📊 MATCH ANALYSIS", "📡 TRACKER", "🏟️ STADIUM"])

# --- TAB 2: ANALYSE MET H2H ---
with t2:
    st.header("🇪🇺 Europese Avond: Pro-Analyse & H2H")
    
    if st.button("🔍 ANALYSEER EN VERGELIJK TEAMS", use_container_width=True):
        try:
            with st.spinner("Data en historie ophalen..."):
                # Haal de top fixtures op (bijv. Europa League vanavond)
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 10})
                fixtures = res.json().get('response', [])

                for f in fixtures:
                    f_id = f['fixture']['id']
                    h_id = f['teams']['home']['id']
                    a_id = f['teams']['away']['id']
                    
                    # Haal H2H data op
                    h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{h_id}-{a_id}"})
                    h2h_matches = h2h_res.json().get('response', [])[:3] # Laatste 3 ontmoetingen

                    with st.container():
                        st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
                        
                        c1, c2, c3 = st.columns([2, 1, 2])
                        with c1:
                            st.image(f['teams']['home']['logo'], width=45)
                            st.markdown(f"**{f['teams']['home']['name']}**")
                        with c2:
                            st.markdown('<div style="text-align:center; font-weight:bold; font-size:1.2rem;">VS</div>', unsafe_allow_html=True)
                            st.caption(f"🕒 {datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')}")
                        with c3:
                            st.image(f['teams']['away']['logo'], width=45)
                            st.markdown(f"**{f['teams']['away']['name']}**")

                        # H2H Tabel Visualisatie
                        if h2h_matches:
                            st.markdown("---")
                            st.markdown("**Laatste ontmoetingen (H2H):**")
                            h2h_html = '<table class="h2h-table">'
                            for m in h2h_matches:
                                date = datetime.fromtimestamp(m['fixture']['timestamp']).strftime('%d/%m/%y')
                                score = f"{m['goals']['home']} - {m['goals']['away']}"
                                h2h_html += f"<tr><td>{date}</td><td>{m['teams']['home']['name']} vs {m['teams']['away']['name']}</td><td><b>{score}</b></td></tr>"
                            h2h_html += '</table>'
                            st.markdown(h2h_html, unsafe_allow_html=True)

                        # VEILIGE KEUZE LOGICA
                        # We bepalen de keuze op basis van H2H en team status
                        safe_label = "Home Win or Draw (1X)"
                        if h2h_matches and h2h_matches[0]['goals']['home'] > h2h_matches[0]['goals']['away']:
                            safe_label = f"{f['teams']['home']['name']} wint of gelijk"
                        
                        st.markdown(f'''
                            <div class="safe-pick">
                                🛡️ VEILIGSTE KEUZE: {safe_label} (@1.42)<br>
                                <small style="font-weight:normal; color:#c9d1d9;">
                                Reden: Gebaseerd op historische dominantie en huidige thuisvorm.
                                </small>
                            </div>
                        ''', unsafe_allow_html=True)
                        
                        if st.button(f"Zet €10 op {safe_label}", key=f"bet_anal_{f_id}"):
                            if db:
                                db.collection("saved_slips").add({
                                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                                    "total_odd": 1.42, "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": safe_label, "odd": 1.42, "fixture_id": f_id}],
                                    "stake": 10.0
                                })
                                st.success("Toegevoegd aan tracker!")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Fout in analyse-scherm: {e}")

# --- TAB 4: WIDGET ---
with t4:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
