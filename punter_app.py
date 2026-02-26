import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Dashboard", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .slip-container { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-top: 4px solid #238636; }
    .match-row { background-color: #1c2128; border-radius: 8px; padding: 12px; margin: 8px 0; border: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
    .score-badge { background: #010409; color: #ffffff; padding: 6px 12px; border-radius: 6px; font-family: 'Roboto Mono', monospace; font-size: 1.2rem; font-weight: bold; border: 1px solid #30363d; min-width: 80px; text-align: center; }
    .live-indicator { color: #f85149; font-weight: bold; font-size: 0.8rem; text-transform: uppercase; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
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

# --- STATE ---
if 'balance' not in st.session_state: st.session_state.balance = 100.0

t1, t2 = st.tabs(["🚀 SLIP GENERATOR", "📡 LIVE TRACKER & PORTFOLIO"])

# [Tab 1: Generator blijft gelijk aan V51]

with t2:
    st.markdown(f"### 📡 Live Portfolio | Saldo: €{st.session_state.balance:.2f}")
    u_id = st.text_input("Bevestig User ID", value="punter_01", key="tracker_uid")
    
    if db:
        try:
            # GEOPTIMALISEERDE QUERY VOOR JE INDEX
            # We gebruiken exact de volgorde: user_id (ASC) en timestamp (DESC)
            docs = (db.collection("saved_slips")
                    .where("user_id", "==", u_id)
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(20)
                    .get())

            if not docs:
                st.info("Geen actieve slips gevonden voor dit ID. Sla eerst een slip op in de Generator.")
            else:
                # Verzamel fixture IDs voor live updates
                f_ids = []
                slips_data = []
                for doc in docs:
                    data = doc.to_dict()
                    data['id'] = doc.id
                    slips_data.append(data)
                    for m in data['matches']:
                        f_ids.append(m['fixture_id'])

                # Haal live scores op
                live_updates = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []):
                            live_updates[f['fixture']['id']] = f

                # Toon de slips
                for s in slips_data:
                    st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                    st.markdown(f"**Slip @{s.get('total_odd', 0)}** | Inzet: €{s.get('stake', 0)}", unsafe_allow_html=True)
                    
                    win_count = 0
                    for m in s['matches']:
                        f_upd = live_updates.get(m['fixture_id'])
                        h_g = f_upd['goals']['home'] if f_upd and f_upd['goals']['home'] is not None else 0
                        a_g = f_upd['goals']['away'] if f_upd and f_upd['goals']['away'] is not None else 0
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        st.markdown(f'<div><div style="color:#c9d1d9; font-weight:bold;">{m["match"]}</div><div style="color:#8b949e; font-size:0.85rem;">{m["market"]} (@{m["odd"]})</div></div>', unsafe_allow_html=True)
                        
                        if f_upd:
                            stat = f_upd['fixture']['status']['short']
                            if stat in ['1H', '2H', 'HT']:
                                st.markdown(f'<div><div class="live-indicator">🔴 {f_upd["fixture"]["status"]["elapsed"]}\'</div>', unsafe_allow_html=True)
                            elif stat == 'FT':
                                win_count += 1
                                st.markdown('<div>🏁 FT', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div>🕒 {m.get("time", "??:??")}', unsafe_allow_html=True)
                        
                        st.markdown(f'<div class="score-badge">{h_g} - {a_g}</div></div></div>', unsafe_allow_html=True)
                    
                    # Cash-out acties
                    col1, col2 = st.columns([3, 1])
                    potential = s.get('stake', 10) * s.get('total_odd', 1)
                    c_val = round(potential * (win_count / len(s['matches'])) * 0.85, 2)
                    
                    if win_count > 0:
                        if col1.button(f"💰 CASH OUT €{max(c_val, 1.0)}", key=f"co_{s['id']}", use_container_width=True):
                            st.session_state.balance += max(c_val, 1.0)
                            db.collection("saved_slips").document(s['id']).delete()
                            st.rerun()
                    
                    if col2.button("🗑️", key=f"del_{s['id']}", use_container_width=True):
                        db.collection("saved_slips").document(s['id']).delete()
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Database Fout: {e}")
            st.info("Check of de index in Firebase Console al de status 'Enabled' heeft.")
