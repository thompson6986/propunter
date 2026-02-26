import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG & STYLING (GEOPTIMALISEERD VOOR SMARTPHONE) ---
st.set_page_config(page_title="Pro Punter Elite V64", page_icon="🕒", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .slip-container { 
        background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; 
        padding: 15px; margin-bottom: 20px; border-top: 4px solid #238636; 
    }
    .match-row { 
        background-color: #1c2128; border-radius: 8px; padding: 12px; margin: 8px 0; 
        border: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; 
    }
    .timer-badge { 
        color: #f85149; font-weight: bold; font-family: 'Roboto Mono', monospace; 
        font-size: 0.9rem; animation: blinker 1.5s linear infinite; 
    }
    .start-time { color: #8b949e; font-size: 0.8rem; font-family: monospace; }
    .score-badge { 
        background: #010409; color: #ffffff; padding: 6px 12px; border-radius: 6px; 
        font-family: monospace; font-size: 1.2rem; border: 1px solid #30363d; min-width: 70px; text-align: center; 
    }
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

if 'balance' not in st.session_state: st.session_state.balance = 100.0
if 'gen_slips' not in st.session_state: st.session_state.gen_slips = []

t1, t2, t3 = st.tabs(["🚀 GENERATOR", "📡 LIVE TRACKER", "🏟️ STADIUM"])

# --- TAB 1: GENERATOR (Met behoud van filters) ---
with t1:
    st.markdown(f"💰 Saldo: **€{st.session_state.balance:.2f}**")
    u_id = st.text_input("User ID", value="punter_01", key="user_id_input")
    
    if st.button("🚀 GENEREER NIEUWE SLIPS", use_container_width=True):
        try:
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
            data = res.json()
            if data.get('response'):
                pool = []
                for f in data['response'][:50]:
                    f_id = f['fixture']['id']
                    # Starttijd berekenen
                    f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                    
                    o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                    o_data = o_res.json()
                    if o_data.get('response'):
                        for bm in o_data['response'][0]['bookmakers']:
                            for bet in bm['bets']:
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
                st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(4)]
        except: st.error("API Fout")

    for i, slip in enumerate(st.session_state.gen_slips):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            st.markdown(f'''
                <div class="match-row">
                    <div>
                        <div style="font-weight:bold;">{m['match']}</div>
                        <div class="start-time">🕒 Start: {m['start_time']} | {m['market']}</div>
                    </div>
                    <div class="score-badge">@{m['odd']}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        stake = st.number_input(f"Inzet (€)", 1.0, 500.0, 10.0, key=f"stake_{i}")
        if st.button(f"✅ PLAATS SLIP @{round(t_odd,2)}", key=f"btn_{i}", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(t_odd,2), "matches": slip, "stake": stake
                })
                st.success("Opgeslagen!"); time.sleep(0.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER (DE FIX) ---
with t2:
    st.markdown("### 📡 Live Tracker & Timer")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(8).get()
        
        if docs:
            # Verzamel alle IDs voor 1 API call (efficiëntie)
            all_ids = [str(m['fixture_id']) for d in docs for m in d.to_dict().get('matches', [])]
            live_data = {}
            if all_ids:
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(all_ids)})
                if res.status_code == 200:
                    for f in res.json().get('response', []):
                        live_data[f['fixture']['id']] = f

            for doc in docs:
                s = doc.to_dict(); s['id'] = doc.id
                st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                st.markdown(f"**Slip @{s.get('total_odd')}** (Inzet: €{s.get('stake')})")
                
                for m in s.get('matches', []):
                    f_info = live_data.get(m['fixture_id'])
                    
                    # Logica voor de Timer en Score
                    status_short = f_info['fixture']['status']['short'] if f_info else "NS"
                    elapsed = f_info['fixture']['status']['elapsed'] if f_info else None
                    h_goals = f_info['goals']['home'] if f_info and f_info['goals']['home'] is not None else 0
                    a_goals = f_info['goals']['away'] if f_info and f_info['goals']['away'] is not None else 0
                    
                    # Bepaal wat we tonen als tijd/timer
                    timer_html = ""
                    if status_short in ['1H', '2H', 'HT']:
                        timer_html = f'<span class="timer-badge">🔴 {elapsed}\'</span>'
                    elif status_short == 'FT':
                        timer_html = '<span style="color:#3fb950; font-weight:bold;">🏁 FT</span>'
                    else:
                        timer_html = f'<span class="start-time">🕒 {m.get("start_time", "NS")}</span>'

                    st.markdown(f'''
                        <div class="match-row">
                            <div>
                                <div style="font-weight:bold;">{m['match']}</div>
                                <div style="font-size:0.8rem; color:#8b949e;">{m['market']}</div>
                                {timer_html}
                            </div>
                            <div class="score-badge">{h_goals} - {a_goals}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                
                if st.button("🗑️ Verwijder", key=f"del_{s['id']}", use_container_width=True):
                    db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Geen actieve slips gevonden.")

with t3:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
