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
st.set_page_config(page_title="Pro Punter V66", page_icon="🕒", layout="wide")
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
        color: #f85149; font-weight: bold; font-family: monospace; 
        font-size: 1rem; animation: blinker 1.5s linear infinite; 
    }
    .time-text { color: #8b949e; font-size: 0.9rem; font-family: monospace; font-weight: bold; }
    .score-badge { 
        background: #010409; color: #ffffff; padding: 6px 12px; border-radius: 6px; 
        font-family: monospace; font-size: 1.3rem; border: 1px solid #30363d; min-width: 75px; text-align: center; 
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

t1, t2, t3 = st.tabs(["🚀 SLIP GENERATOR", "📡 LIVE TRACKER", "🏟️ STADIUM"])

# --- TAB 1: GENERATOR (MET STARTTIJDEN) ---
with t1:
    st.markdown(f"💰 Saldo: **€{st.session_state.balance:.2f}**")
    u_id = st.text_input("User ID", value="punter_01")
    
    if st.button("🚀 GENEREER VOORSTEL SLIPS", use_container_width=True):
        try:
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
            data = res.json()
            if data.get('response'):
                pool = []
                # Neem meer wedstrijden voor betere spreiding
                for f in data['response'][:60]:
                    # STARTTIJD UIT API HALEN
                    f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                    f_id = f['fixture']['id']
                    
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
                                            "start_time": f_time # Hier leggen we de tijd vast!
                                        })
                st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(4)]
        except: st.error("Fout bij ophalen live data.")

    for i, slip in enumerate(st.session_state.gen_slips):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            # WEERGAVE TIJD IN VOORSTEL
            st.markdown(f'''
                <div class="match-row">
                    <div>
                        <div style="font-weight:bold;">{m['match']}</div>
                        <div class="time-text">🕒 {m.get('start_time', 'Live')} | {m['market']}</div>
                    </div>
                    <div class="score-badge">@{m['odd']}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        stake = st.number_input(f"Inzet (€)", 1.0, 500.0, 10.0, key=f"st_{i}")
        if st.button(f"✅ BEVESTIG SLIP @{round(t_odd,2)}", key=f"btn_{i}", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(t_odd,2), "matches": slip, "stake": stake
                })
                st.success("Succesvol geplaatst!"); time.sleep(0.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER (STARTTIJD + LIVE TIMER) ---
with t2:
    st.markdown("### 📡 Actuele Tracker")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        
        if docs:
            # Efficiëntie: alle fixture IDs ophalen
            all_ids = [str(m['fixture_id']) for d in docs for m in d.to_dict().get('matches', [])]
            live_data = {}
            if all_ids:
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(all_ids)})
                if res.status_code == 200:
                    for f in res.json().get('response', []): live_data[f['fixture']['id']] = f

            for doc in docs:
                s = doc.to_dict(); s['id'] = doc.id
                st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                st.markdown(f"**Slip @{s.get('total_odd')}** | Inzet: €{s.get('stake', 10)}")
                
                for m in s.get('matches', []):
                    f_info = live_data.get(m['fixture_id'])
                    
                    status = f_info['fixture']['status']['short'] if f_info else "NS"
                    elapsed = f_info['fixture']['status']['elapsed'] if f_info else None
                    h_g = f_info['goals']['home'] if f_info and f_info['goals']['home'] is not None else 0
                    a_g = f_info['goals']['away'] if f_info and f_info['goals']['away'] is not None else 0
                    
                    # Logica: Live Timer of Starttijd
                    time_display = ""
                    if status in ['1H', '2H', 'HT']:
                        time_display = f'<div class="timer-badge">🔴 {elapsed}\'</div>'
                    elif status == 'FT':
                        time_display = '<div style="color:#3fb950; font-weight:bold;">🏁 FT</div>'
                    else:
                        # Haal opgeslagen starttijd op uit DB
                        st_time = m.get('start_time', '??:??')
                        time_display = f'<div class="time-text">🕒 Start: {st_time}</div>'

                    st.markdown(f'''
                        <div class="match-row">
                            <div>
                                <div style="font-weight:bold; color:#f0f6fc;">{m['match']}</div>
                                <div style="font-size:0.8rem; color:#8b949e;">{m['market']}</div>
                                {time_display}
                            </div>
                            <div class="score-badge">{h_g} - {a_g}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                
                if st.button("🗑️ Verwijder", key=f"del_{s['id']}", use_container_width=True):
                    db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("Geen actieve slips.")

with t3:
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
