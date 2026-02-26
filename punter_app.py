import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter V62 - Strict Markets", page_icon="🏦", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; border-left: 5px solid #1f6feb; }
    .slip-container { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-top: 4px solid #238636; }
    .match-row { background-color: #1c2128; border-radius: 8px; padding: 15px; margin: 8px 0; border: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
    .score-badge { background: #010409; color: #ffffff; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 1.3rem; border: 1px solid #30363d; min-width: 85px; text-align: center; }
    .live-indicator { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
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

t1, t2, t3 = st.tabs(["🚀 TARGET GENERATOR", "📡 PORTFOLIO", "🏟️ LIVE STADIUM"])

# --- TAB 1: GENERATOR (STRICT FILTERS) ---
with t1:
    st.markdown(f"### 💰 Bankroll: **€{st.session_state.balance:.2f}**")
    
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        target_odd = c1.selectbox("Doel Odds", [1.5, 2.0, 3.0, 5.0])
        m_count = c2.slider("Aantal Wedstrijden", 1, 4, 2)
        u_id = st.text_input("User ID", value="punter_01")
        st.info("Actieve Markten: Win FT, Over/Under 1.5/2.5, BTTS. (Asian & Corners uitgeschakeld)")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER PROFESSIONELE SLIPS", use_container_width=True):
        try:
            with st.spinner("Scannen van toegestane markten..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response'][:75]:
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f['fixture']['id']})
                        o_data = o_res.json()
                        
                        if o_data.get('response'):
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    # --- STRIKTE MARKT VALIDATIE ---
                                    is_allowed = False
                                    m_name = bet['name']
                                    
                                    if m_name == "Match Winner":
                                        is_allowed = True
                                    elif m_name == "Both Teams Score":
                                        is_allowed = True
                                    elif m_name == "Goals Over/Under":
                                        # Filter enkel voor 1.5 en 2.5
                                        is_allowed = True 

                                    if is_allowed:
                                        for val in bet['values']:
                                            v_str = str(val['value'])
                                            # Extra check: geen Asian, geen Corners, geen afwijkende lines
                                            if any(x in v_str for x in ["Asian", "Corner", "0.75", "1.25", "2.25", "2.75", "3.5", "4.5"]): 
                                                continue
                                            
                                            # Alleen Over/Under 1.5 en 2.5 behouden voor Goals markt
                                            if m_name == "Goals Over/Under" and not any(x in v_str for x in ["1.5", "2.5"]):
                                                continue

                                            odd = float(val['odd'])
                                            pool.append({
                                                "fixture_id": f['fixture']['id'], 
                                                "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                "market": f"{m_name}: {v_str}", 
                                                "odd": odd, 
                                                "time": datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                                            })
                    
                    # Slip Constructie
                    valid_results = []
                    for _ in range(20):
                        if len(pool) >= m_count:
                            cand = random.sample(pool, m_count)
                            total = 1.0
                            for m in cand: total *= m['odd']
                            if (target_odd * 0.9) <= total <= (target_odd * 1.3):
                                valid_results.append(cand)
                    
                    st.session_state.gen_slips = valid_results[:4]
        except Exception as e:
            st.error(f"Fout bij scannen: {e}")

    for i, slip in enumerate(st.session_state.gen_slips):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            st.markdown(f'<div class="match-row"><div><b>{m["match"]}</b><br><span style="color:#8b949e; font-size:0.85rem;">🕒 {m["time"]} | {m["market"]}</span></div><div class="score-badge">@{m["odd"]}</div></div>', unsafe_allow_html=True)
        
        t_odd = round(t_odd, 2)
        c_a, c_b = st.columns([2, 1])
        stake = c_a.number_input(f"Inzet (€)", 1.0, 1000.0, 10.0, key=f"s_{i}")
        if c_b.button(f"✅ PLAATS @{t_odd}", key=f"p_{i}", use_container_width=True):
            if db:
                db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": t_odd, "matches": slip, "stake": stake})
                st.toast("Bet Opgeslagen!"); time.sleep(0.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2 & 3 (PORTFOLIO & WIDGET) ---
with t2:
    st.markdown("### 📡 Actieve Tracker")
    # [Zelfde robuuste tracker logica als V61...]
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        for doc in docs:
            s = doc.to_dict(); s['id'] = doc.id
            st.markdown('<div class="slip-container">', unsafe_allow_html=True)
            st.write(f"**Slip @{s.get('total_odd')}** | Inzet: €{s.get('stake')}")
            for m in s.get('matches', []):
                st.markdown(f'<div class="match-row"><div>{m["match"]}<br><small>{m["market"]}</small></div><div class="score-badge">@{m["odd"]}</div></div>', unsafe_allow_html=True)
            if st.button("🗑️ Verwijder", key=f"del_{s['id']}"):
                db.collection("saved_slips").document(s['id']).delete(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with t3:
    widget_html = f"""
    <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
    <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """
    components.html(widget_html, height=1000, scrolling=True)
