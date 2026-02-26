import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter V69", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .slip-card { border: 1px solid #30363d; padding: 18px; border-radius: 12px; margin-bottom: 20px; background: #161b22; border-left: 5px solid #238636; }
    .match-line { border-bottom: 1px solid #30363d; padding: 10px 0; }
    .match-line:last-child { border-bottom: none; }
    .market-label { color: #8b949e; font-size: 0.85rem; font-style: italic; }
    .timer-live { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; font-family: monospace; }
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
t1, t2, t3 = st.tabs(["🚀 GENERATOR", "📡 LIVE TRACKER", "🏟️ STADIUM"])

# --- TAB 1: GENERATOR (ONGEWIJZIGD) ---
with t1:
    u_id = st.text_input("User ID", value="punter_01")
    if st.button("🚀 SCAN MARKT", use_container_width=True):
        try:
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS', 'next': 15}) 
            data = res.json()
            if data.get('response'):
                pool = []
                for f in data['response']:
                    f_id = f['fixture']['id']
                    f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                    o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
                    o_data = o_res.json()
                    if o_data.get('response'):
                        for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                            if bet['name'] in ["Match Winner", "Both Teams Score", "Goals Over/Under"]:
                                for val in bet['values']:
                                    if any(x in str(val['value']) for x in ["Asian", "Corner", "3.5", "4.5"]): continue
                                    pool.append({
                                        "fixture_id": f_id, 
                                        "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                        "market": f"{bet['name']}: {val['value']}", 
                                        "odd": float(val['odd']), 
                                        "start_time": f_time
                                    })
                if pool: st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(3)]
        except: st.error("API limiet.")

    if 'gen_slips' in st.session_state:
        for i, slip in enumerate(st.session_state.gen_slips):
            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
            t_o = 1.0
            for m in slip:
                t_o *= m.get('odd', 1.0)
                st.write(f"🕒 {m.get('start_time')} | **{m.get('match')}**")
                st.markdown(f'<span class="market-label">{m.get("market")} (@{m.get("odd")})</span>', unsafe_allow_html=True)
            
            if st.button(f"✅ PLAATS SLIP @{round(t_o, 2)}", key=f"p_{i}"):
                if db:
                    db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": round(t_o, 2), "matches": slip, "stake": 10.0})
                    st.success("Geplaatst!"); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER (FIXED) ---
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
                st.markdown(f'<div class="slip-card"><b>Slip @{s.get("total_odd")}</b> (Inzet: €{s.get("stake", 10)})', unsafe_allow_html=True)
                
                for m in s.get('matches', []):
                    f_info = live_map.get(m.get('fixture_id'))
                    
                    # Live Data herstellen
                    status = f_info['fixture']['status']['short'] if f_info else "NS"
                    score = f"{f_info['goals']['home']} - {f_info['goals']['away']}" if f_info and f_info['goals']['home'] is not None else "0 - 0"
                    elapsed = f_info['fixture']['status']['elapsed'] if f_info else None
                    
                    # Weergave tijd/minuut
                    timer_html = ""
                    if status in ['1H', '2H', 'HT']:
                        timer_html = f'<span class="timer-live">🔴 {elapsed}\'</span>'
                    elif status == 'FT':
                        timer_html = '<span style="color:#3fb950;">🏁 FT</span>'
                    else:
                        timer_html = f'<span style="color:#8b949e;">🕒 {m.get("start_time", "NS")}</span>'

                    # DE FIX: Weergave van de wedmarkt in de tracker
                    st.markdown(f'''
                        <div class="match-line">
                            <div style="display:flex; justify-content:space-between;">
                                <span>{timer_html} <b>{m.get('match')}</b></span>
                                <span style="font-family:monospace; font-weight:bold;">{score}</span>
                            </div>
                            <div class="market-label">Gok: {m.get('market')} (@{m.get('odd')})</div>
                        </div>
                    ''', unsafe_allow_html=True)
                
                if st.button("🗑️ Verwijder", key=f"d_{s['id']}", use_container_width=True):
                    db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("Geen actieve slips.")

with t3:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
