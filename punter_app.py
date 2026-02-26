import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG & STYLING ---
st.set_page_config(page_title="OddAlerts Pro", page_icon="🔔", layout="wide")

# Custom CSS voor de OddAlerts Look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2127; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .bet-card { 
        background-color: #161b22; 
        padding: 20px; 
        border-radius: 12px; 
        border-left: 5px solid #238636;
        margin-bottom: 15px;
        border-right: 1px solid #30363d;
        border-top: 1px solid #30363d;
        border-bottom: 1px solid #30363d;
    }
    .status-live { color: #238636; font-weight: bold; font-size: 0.8rem; }
    .prob-high { color: #2ea043; font-weight: bold; }
    .prob-mid { color: #d29922; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTEN ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- DB INIT ---
if "firebase" in st.secrets and not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)
db = firestore.client() if firebase_admin._apps else None

# --- STATE ---
if 'bankroll' not in st.session_state: st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state: st.session_state.active_bets = []
if 'slips' not in st.session_state: st.session_state.slips = {}

# --- SIDEBAR (CONTROLS) ---
with st.sidebar:
    st.title("🔔 OddAlerts Dashboard")
    user_id = st.text_input("Punter ID", value="pro_user_1")
    
    st.divider()
    st.metric("BANKROLL", f"€{st.session_state.bankroll:.2f}")
    min_pct = st.slider("Min. Probability %", 10, 90, 25)
    
    if st.button("🗑️ RESET & REFUND"):
        refund = sum(float(b['Inzet']) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        st.success("Bankroll hersteld.")
        st.rerun()

# --- MAIN INTERFACE ---
col_head, col_action = st.columns([3, 1])
with col_head:
    st.title("Market Scanner")
    st.caption(f"📅 {datetime.now().strftime('%d %B %Y')} | API Status: 🟢 Active (7500 req/d)")

with col_action:
    if st.button("🚀 SCAN LIVE MARKETS", use_container_width=True):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        params = {'date': datetime.now().strftime('%Y-%m-%d')}
        
        try:
            r = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
            data = r.json()
            
            if r.status_code == 200 and data.get('response'):
                targets = [1.5, 2.0, 3.0, 5.0]
                new_slips = {}
                
                for t in targets:
                    best_match = None
                    best_diff = 1.0
                    for item in data['response']:
                        for bm in item['bookmakers']:
                            if bm['name'] in ['Bet365', '1xBet', 'Bwin']:
                                for bet in bm['bets']:
                                    for val in bet['values']:
                                        odd = float(val['odd'])
                                        prob = (1/odd)*100
                                        diff = abs(odd - t)
                                        if diff < best_diff and prob >= min_pct:
                                            best_diff = diff
                                            best_match = {
                                                "teams": f"{item['fixture']['timezone']} | {item['league']['name']}",
                                                "match": f"{item['league']['country']} - {item['league']['name']}",
                                                "target_odd": t,
                                                "live_odd": odd,
                                                "market": f"{bet['name']}: {val['value']}",
                                                "prob": round(prob, 1)
                                            }
                    if best_match: new_slips[t] = best_match
                st.session_state.slips = new_slips
        except: st.error("API Connectie fout.")

# --- DISPLAY GRID ---
if st.session_state.slips:
    cols = st.columns(4)
    for i, t in enumerate([1.5, 2.0, 3.0, 5.0]):
        with cols[i]:
            if t in st.session_state.slips:
                s = st.session_state.slips[t]
                prob_class = "prob-high" if s['prob'] > 50 else "prob-mid"
                
                st.markdown(f"""
                <div class="bet-card">
                    <span class="status-live">● TARGET @{t}</span>
                    <h3 style="margin: 10px 0;">@{s['live_odd']}</h3>
                    <p style="font-size: 0.9rem; color: #8b949e;">{s['teams']}</p>
                    <p style="font-weight: bold;">{s['market']}</p>
                    <p class="{prob_class}">Model Probability: {s['prob']}%</p>
                </div>
                """, unsafe_allow_html=True)
                
                stake = st.number_input(f"Stake €", min_value=1.0, value=10.0, key=f"stake_{t}")
                if st.button(f"PLACE BET @{s['live_odd']}", key=f"btn_{t}", use_container_width=True):
                    if st.session_state.bankroll >= stake:
                        st.session_state.bankroll -= stake
                        st.session_state.active_bets.append({
                            "Match": s['teams'], "Odd": s['live_odd'], "Inzet": stake, "Markt": s['market']
                        })
                        st.toast("Bet Added to Portfolio!")
                        st.rerun()

st.divider()

# --- PORTFOLIO SECTION ---
st.subheader("📊 Active Alert Portfolio")
if st.session_state.active_bets:
    for b in st.session_state.active_bets:
        with st.expander(f"⚽ {b['Match']} | @{b['Odd']} | €{b['Inzet']}"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Markt:** {b['Markt']}")
            c2.write(f"**Status:** 🏃 In Play")
            c3.button("Cash Out (Fix)", key=f"cash_{time.time()}")
else:
    st.info("No active alerts set.")
