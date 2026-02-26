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
st.set_page_config(page_title="Pro Punter V72", page_icon="⚙️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .control-panel { background-color: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; margin-bottom: 25px; }
    .slip-card { border: 1px solid #30363d; padding: 18px; border-radius: 12px; margin-bottom: 20px; background: #0d1117; border-top: 4px solid #238636; }
    .timer-live { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
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

# --- TABS ---
t1, t2, t3 = st.tabs(["⚙️ GENERATOR INSTELLINGEN", "📡 LIVE TRACKER", "🏟️ STADIUM"])

with t1:
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    st.subheader("🛠️ Handmatige Filters")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        hours_ahead = st.slider("Tijdspanne (uren vanaf nu)", 1, 24, 6)
        min_prob = st.slider("Min. Waarschijnlijkheid (%)", 10, 90, 50)
    with col2:
        min_odd = st.number_input("Min. Odds per match", 1.10, 5.0, 1.30)
        max_odd = st.number_input("Max. Odds per match", 1.10, 10.0, 3.0)
    with col3:
        markets = st.multiselect("Markten", ["Match Winner", "Both Teams Score", "Goals Over/Under"], ["Match Winner", "Both Teams Score"])
        u_id = st.text_input("User ID", value="punter_01")
    
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🔍 SCAN WEDSTRIJDEN MET FILTERS", use_container_width=True):
        try:
            with st.spinner("Markt scannen op basis van jouw parameters..."):
                now = datetime.now(TIMEZONE)
                limit_time = now + timedelta(hours=hours_ahead)
                
                today = now.strftime('%Y-%m-%d')
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'})
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response']:
                        f_dt = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE)
                        
                        # Filter op tijdspanne
                        if now <= f_dt <= limit_time:
                            f_id = f['fixture']['id']
                            f_time = f_dt.strftime('%H:%M')
                            
                            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
                            o_data = o_res.json()
                            
                            if o_data.get('response'):
                                for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                                    if bet['name'] in markets:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            prob = (1 / odd) * 100
                                            
                                            # Filter op Odds en Waarschijnlijkheid
                                            if min_odd <= odd <= max_odd and prob >= min_prob:
                                                if any(x in str(val['value']) for x in ["Asian", "Corner", "3.5", "4.5"]): continue
                                                pool.append({
                                                    "fixture_id": f_id,
                                                    "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                                    "market": f"{bet['name']}: {val['value']}",
                                                    "odd": odd,
                                                    "prob": round(prob, 1),
                                                    "start_time": f_time
                                                })
                    st.session_state.custom_pool = pool
                    st.success(f"Gevonden: {len(pool)} wedstrijden die aan je eisen voldoen.")
        except: st.error("API Fout. Controleer verbinding.")

    # Weergave van de gevonden pool als 'Voorstel Slips'
    if st.session_state.get('custom_pool'):
        st.markdown("### 📋 Beschikbare Matches (Berekend)")
        for i, m in enumerate(st.session_state.custom_pool):
            with st.container():
                st.markdown(f'''
                    <div class="slip-card">
                        <div style="display:flex; justify-content:space-between;">
                            <span>🕒 {m['start_time']} | <b>{m['match']}</b></span>
                            <span style="color:#238636; font-weight:bold;">{m['prob']}% Kans</span>
                        </div>
                        <div style="color:#8b949e; margin: 5px 0;">{m['market']}</div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                            <span style="font-size:1.2rem; font-weight:bold;">@{m['odd']}</span>
                            <button onclick="window.location.reload();" style="background:#238636; color:white; border:none; padding:5px 15px; border-radius:5px;">Selecteer</button>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
                # Omdat Streamlit buttons in HTML lastig zijn, hier een simpele 'Save' knop per match:
                if st.button(f"Bevestig Weddenschap: {m['match']} (@{m['odd']})", key=f"save_{i}"):
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                            "total_odd": m['odd'], "matches": [m], "stake": 10.0
                        })
                        st.toast("Match toegevoegd aan tracker!")

# --- TAB 2: LIVE TRACKER (Zelfde als V71, blijft stabiel) ---
with t2:
    st.markdown("### 📡 Live Tracker")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        if docs:
            all_ids = [str(m.get('fixture_id')) for d in docs for m in d.to_dict().get('matches', [])]
            live_map = {}
            if all_ids:
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(set(all_ids))})
                if res.status_code == 200:
                    live_map = {f['fixture']['id']: f for f in res.json().get('response', [])}

            for doc in docs:
                s = doc.to_dict(); s['id'] = doc.id
                st.markdown(f'<div class="slip-card"><b>Slip @{s.get("total_odd")}</b>', unsafe_allow_html=True)
                for m in s.get('matches', []):
                    f_info = live_map.get(m.get('fixture_id'))
                    status = f_info['fixture']['status']['short'] if f_info else "NS"
                    score = f"{f_info['goals']['home']} - {f_info['goals']['away']}" if f_info and f_info['goals']['home'] is not None else "0 - 0"
                    elapsed = f_info['fixture']['status']['elapsed'] if f_info else None
                    
                    time_label = f'<span class="timer-live">🔴 {elapsed}\'</span>' if status in ['1H', '2H', 'HT'] else f'🕒 {m.get("start_time", "NS")}'
                    if status == 'FT': time_label = '🏁 FT'
                    
                    st.write(f"{time_label} | **{m['match']}** | {score}")
                    st.caption(f"Gok: {m['market']} (@{m['odd']})")
                if st.button("🗑️", key=f"del_{s['id']}"):
                    db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
