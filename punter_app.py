import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Live Betting Dashboard", page_icon="⚽", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; font-weight: bold; }
    .control-panel { background-color: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 20px; }
    .slip-container { background-color: #0d1117; border: 2px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 30px; }
    .match-row { background-color: #161b22; border-radius: 8px; padding: 15px; margin: 10px 0; border: 1px solid #21262d; }
    .live-timer { color: #f85149; font-weight: bold; font-size: 1rem; animation: blinker 1.5s linear infinite; }
    .score-box { background: #000; color: #fff; padding: 5px 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 1.4rem; font-weight: bold; border: 1px solid #58a6ff; }
    .time-badge { color: #8b949e; font-size: 0.9rem; }
    @keyframes blinker { 50% { opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

# --- DB & API CONFIG ---
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
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 LIVE TRACKER"])

# [Tab 1: Generator blijft ongewijzigd]

with t2:
    st.title("📡 Live Tracker Dashboard")
    user_id = st.text_input("User ID", value="punter_01")
    
    if db:
        try:
            saved = (db.collection("saved_slips")
                     .where("user_id", "==", user_id)
                     .order_by("timestamp", direction=firestore.Query.DESCENDING)
                     .limit(10).get())
            
            if not saved:
                st.info("Geen actieve slips in je portfolio.")
            else:
                f_ids = []
                docs = []
                for d in saved:
                    data = d.to_dict(); data['id'] = d.id; docs.append(data)
                    for m in data['matches']: f_ids.append(m['fixture_id'])
                
                # Fetch LIVE DATA
                live_updates = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []):
                            live_updates[f['fixture']['id']] = f

                # Display Slips (OPEN - Geen Expander meer)
                for s in docs:
                    st.markdown(f'<div class="slip-container">', unsafe_allow_html=True)
                    st.subheader(f"Slip Odds: @{s['total_odd']} (Opgeslagen om {s['timestamp'].strftime('%H:%M')})")
                    
                    win_count = 0
                    for m in s['matches']:
                        f_id = m['fixture_id']
                        f_data = live_updates.get(f_id)
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        c1, c2, c3 = st.columns([3, 2, 1])
                        
                        with c1:
                            st.markdown(f"**{m['match']}**")
                            st.caption(f"🎯 {m['market']} (@{m['odd']})")
                        
                        with c2:
                            if f_data:
                                status = f_data['fixture']['status']['short']
                                h_g = f_data['goals']['home']
                                a_g = f_data['goals']['away']
                                elapsed = f_data['fixture']['status']['elapsed']
                                
                                if status in ['1H', '2H', 'HT']:
                                    st.markdown(f"<span class='live-timer'>🔴 {status} {elapsed}'</span>", unsafe_allow_html=True)
                                    st.markdown(f"<span class='score-box'>{h_g} - {a_g}</span>", unsafe_allow_html=True)
                                elif status == 'FT':
                                    win_count += 1
                                    st.markdown(f"🏁 **FT** <span class='score-box'>{h_g} - {a_g}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<span class='time-badge'>🕒 Start: {m['time']}</span>", unsafe_allow_html=True)
                                    st.markdown(f"<span class='score-box'>0 - 0</span>", unsafe_allow_html=True)
                        
                        with c3:
                            # Eenvoudige settlement indicator
                            if f_data and status == 'FT':
                                st.write("✅ Match Voltooid")
                            else:
                                st.write("⏳ In spel")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Cashout & Actions
                    ca1, ca2 = st.columns([3, 1])
                    if win_count > 0:
                        cash_val = round((10 * s['total_odd']) * (win_count / len(s['matches'])) * 0.82, 2)
                        ca1.success(f"💰 Cash-out Beschikbaar: €{max(cash_val, 1.0)}")
                    
                    if ca2.button("🗑️ Verwijder Slip", key=f"del_{s['id']}"):
                        db.collection("saved_slips").document(s['id']).delete()
                        st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        except:
            st.warning("De database index wordt nog geconfigureerd. Een moment geduld...")
