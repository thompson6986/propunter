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
st.set_page_config(page_title="Pro Punter V71", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .slip-card { border: 1px solid #30363d; padding: 18px; border-radius: 12px; margin-bottom: 20px; background: #161b22; border-left: 5px solid #238636; }
    .match-line { border-bottom: 1px solid #30363d; padding: 10px 0; display: flex; flex-direction: column; }
    .market-info { color: #8b949e; font-size: 0.85rem; font-weight: bold; margin-top: 4px; }
    .timer-live { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; font-family: monospace; }
    .score-badge { background: #010409; color: #ffffff; padding: 5px 10px; border-radius: 6px; font-family: monospace; font-size: 1.2rem; border: 1px solid #30363d; }
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

# --- UI TABS ---
t1, t2, t3 = st.tabs(["🚀 ELITE GENERATOR", "📡 LIVE TRACKER", "🏟️ STADIUM"])

# --- TAB 1: GENERATOR (BREDE SCAN) ---
with t1:
    st.markdown(f"### 💰 Bankroll: **€{st.session_state.get('balance', 100):.2f}**")
    c1, c2 = st.columns(2)
    target_odd = c1.selectbox("Doel Odds Totaal", [1.5, 2.0, 3.0, 5.0])
    u_id = c2.text_input("User ID", value="punter_01")

    if st.button("🚀 GENEREER VOORSTELLEN (BREDE SCAN)", use_container_width=True):
        try:
            with st.spinner("Analyseren van 50+ wedstrijden..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                # We scannen nu meer wedstrijden voor variatie
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS', 'next': 50}) 
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response']:
                        f_id = f['fixture']['id']
                        f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                        
                        # Odds ophalen voor Win FT, O/U en BTTS
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
                        o_data = o_res.json()
                        
                        if o_data.get('response') and len(o_data['response']) > 0:
                            for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                                if bet['name'] in ["Match Winner", "Both Teams Score", "Goals Over/Under"]:
                                    for val in bet['values']:
                                        if any(x in str(val['value']) for x in ["Asian", "Corner", "3.5", "4.5"]): continue
                                        pool.append({
                                            "fixture_id": f_id, 
                                            "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                            "market": f"{bet['name']}: {val['value']}", 
                                            "odd": float(val['odd']), "start_time": f_time
                                        })
                    
                    # Maak combinaties die passen bij de target_odd
                    results = []
                    for _ in range(20):
                        if len(pool) >= 2:
                            cand = random.sample(pool, 2) # Slips van 2 matchen voor stabiliteit
                            total = 1.0
                            for m in cand: total *= m['odd']
                            if (target_odd * 0.85) <= total <= (target_odd * 1.3):
                                results.append(cand)
                    st.session_state.gen_slips = results[:4]
        except: st.error("Fout bij data-analyse.")

    if st.session_state.get('gen_slips'):
        for i, slip in enumerate(st.session_state.gen_slips):
            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
            total_o = 1.0
            for m in slip:
                total_o *= m['odd']
                st.write(f"🕒 {m.get('start_time')} | **{m['match']}**")
                st.markdown(f'<div class="market-info">{m["market"]} (@{m["odd"]})</div>', unsafe_allow_html=True)
            
            if st.button(f"✅ PLAATS @{round(total_o, 2)}", key=f"p_{i}", use_container_width=True):
                if db:
                    db.collection("saved_slips").add({
                        "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                        "total_odd": round(total_o, 2), "matches": slip, "stake": 10.0
                    })
                    st.toast("Succes!"); time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER (VOLLEDIG HERSTELD) ---
with t2:
    st.markdown("### 📡 Live Portfolio")
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
                    status = f_info['fixture']['status']['short'] if f_info else "NS"
                    score = f"{f_info['goals']['home']} - {f_info['goals']['away']}" if f_info and f_info['goals']['home'] is not None else "0 - 0"
                    
                    time_label = ""
                    if status in ['1H', '2H', 'HT']:
                        time_label = f'<span class="timer-live">🔴 {f_info["fixture"]["status"]["elapsed"]}\'</span>'
                    elif status == 'FT':
                        time_label = '<span style="color:#3fb950; font-weight:bold;">🏁 FT</span>'
                    else:
                        time_label = f'<span style="color:#8b949e;">🕒 {m.get("start_time", "NS")}</span>'

                    st.markdown(f'''
                        <div class="match-line">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span>{time_label} <b>{m.get('match')}</b></span>
                                <span class="score-badge">{score}</span>
                            </div>
                            <div class="market-info">Gok: {m.get('market')}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                
                if st.button("🗑️ Verwijder Slip", key=f"d_{s['id']}", use_container_width=True):
                    db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
