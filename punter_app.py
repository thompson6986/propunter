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
st.set_page_config(page_title="Pro Punter Elite V61", page_icon="🏦", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-container { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-top: 4px solid #238636; }
    .match-row { background-color: #1c2128; border-radius: 8px; padding: 15px; margin: 8px 0; border: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
    .score-badge { background: #010409; color: #ffffff; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 1.3rem; border: 1px solid #30363d; min-width: 85px; text-align: center; }
    .bankroll-info { background-color: #23863622; color: #3fb950; padding: 10px; border-radius: 8px; border: 1px solid #238636; margin-bottom: 15px; font-weight: bold; }
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

# --- STATE MANAGEMENT ---
if 'balance' not in st.session_state: st.session_state.balance = 100.0
if 'gen_slips' not in st.session_state: st.session_state.gen_slips = []

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 ELITE GENERATOR", "📡 LIVE PORTFOLIO", "🏟️ LIVE STADIUM WIDGET"])

# --- TAB 1: GENERATOR ---
with t1:
    st.markdown(f"### 💰 Saldo: **€{st.session_state.balance:.2f}**")
    suggested_stake = round(st.session_state.balance * 0.05, 2)
    st.markdown(f'<div class="bankroll-info">💡 Staking Plan: Advies €{suggested_stake} per slip</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        target_odd = c1.selectbox("Doel Odds Totaal", [1.5, 2.0, 3.0, 5.0, 10.0])
        m_count = c2.slider("Aantal Matchen", 1, 6, 3)
        u_id = st.text_input("User ID", value="punter_01")
        
        st.write("**Markt Filters:**")
        f1, f2, f3, f4 = st.columns(4)
        m_1x2 = f1.checkbox("1X2 / DC", value=True)
        m_ou = f2.checkbox("Over/Under", value=True)
        m_dnb = f3.checkbox("Draw No Bet", value=True)
        m_fh = f4.checkbox("1st Half Goals", value=False)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 SCAN MARKT VOOR VALUE", use_container_width=True):
        try:
            with st.spinner("Analyse van live odds..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                data = res.json()
                if data.get('response'):
                    pool = []
                    for f in data['response'][:60]:
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f['fixture']['id']})
                        o_data = o_res.json()
                        if o_data.get('response'):
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    allowed = (m_1x2 and bet['name'] in ["Match Winner", "Double Chance"]) or \
                                              (m_ou and "Over/Under" in bet['name']) or \
                                              (m_dnb and "Draw No Bet" in bet['name']) or \
                                              (m_fh and "First Half" in bet['name'])
                                    if allowed:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            if 1.25 <= odd <= 4.0:
                                                pool.append({
                                                    "fixture_id": f['fixture']['id'], 
                                                    "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                    "market": f"{bet['name']}: {val['value']}", 
                                                    "odd": odd, "time": datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                                                })
                    
                    results = []
                    for _ in range(10):
                        if len(pool) >= m_count:
                            cand = random.sample(pool, m_count)
                            to = 1.0
                            for m in cand: to *= m['odd']
                            if (target_odd * 0.8) <= to <= (target_odd * 1.4):
                                results.append(cand)
                    st.session_state.gen_slips = results if results else [random.sample(pool, m_count)]
        except: st.error("Fout bij ophalen data.")

    for i, slip in enumerate(st.session_state.gen_slips[:4]):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            st.markdown(f'<div class="match-row"><div><div style="font-weight:bold;">{m["match"]}</div><div style="color:#8b949e; font-size:0.85rem;">🕒 {m["time"]} | {m["market"]}</div></div><div class="score-badge">@{m["odd"]}</div></div>', unsafe_allow_html=True)
        
        t_odd = round(t_odd, 2)
        c_a, c_b = st.columns([2, 1])
        stake = c_a.number_input(f"Inzet Slip {i+1}", 1.0, 5000.0, 10.0, key=f"s_{i}")
        if c_b.button(f"✅ PLAATS @{t_odd}", key=f"p_{i}", use_container_width=True):
            if db:
                db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": t_odd, "matches": slip, "stake": stake})
                st.toast("Bet Geplaatst!"); time.sleep(0.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE PORTFOLIO ---
with t2:
    st.markdown(f"### 📡 Portfolio Monitoring")
    if db:
        try:
            docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
            if docs:
                f_ids = list(set([m['fixture_id'] for d in docs for m in d.to_dict().get('matches', [])]))
                live_map = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, f_ids))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []): live_map[f['fixture']['id']] = f

                for doc in docs:
                    s = doc.to_dict(); s['id'] = doc.id
                    st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                    st.markdown(f"**Slip @{s.get('total_odd')}** | Inzet: €{s.get('stake')}")
                    
                    won = 0
                    for m in s.get('matches', []):
                        f_upd = live_map.get(m['fixture_id'])
                        h_g = f_upd['goals']['home'] if f_upd and f_upd['goals']['home'] is not None else 0
                        a_g = f_upd['goals']['away'] if f_upd and f_upd['goals']['away'] is not None else 0
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        st.markdown(f'<div><div style="font-weight:bold;">{m["match"]}</div><div style="color:#8b949e; font-size:0.8rem;">{m["market"]} (@{m["odd"]})</div></div>', unsafe_allow_html=True)
                        if f_upd:
                            status = f_upd['fixture']['status']['short']
                            if status in ['1H', '2H', 'HT']:
                                st.markdown(f'<div><div class="live-indicator">🔴 {f_upd["fixture"]["status"]["elapsed"]}\'</div></div>', unsafe_allow_html=True)
                            elif status == 'FT':
                                won += 1; st.markdown('<div>🏁 FT</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="score-badge">{h_g} - {a_g}</div></div>', unsafe_allow_html=True)
                    
                    c_val = round((s.get('stake', 10) * s.get('total_odd', 1)) * (won / len(s.get('matches', [1]))) * 0.90, 2)
                    co1, co2 = st.columns([3, 1])
                    if won > 0:
                        if co1.button(f"💰 CASH OUT €{max(c_val, 1.0)}", key=f"co_{s['id']}", use_container_width=True):
                            st.session_state.balance += max(c_val, 1.0)
                            db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    if co2.button("🗑️", key=f"del_{s['id']}", use_container_width=True):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else: st.info("Geen actieve posities.")
        except Exception as e: st.error(f"Sync error: {e}")

# --- TAB 3: LIVE STADIUM WIDGET ---
with t3:
    st.title("🏟️ Live Stadium Dashboard")
    st.write("Real-time uitslagen en diepgaande match-statistieken.")
    
    widget_html = f"""
    <div id="wg-api-football-livescore"
        data-host="v3.football.api-sports.io"
        data-key="{API_KEY}"
        data-refresh="60"
        data-theme="dark"
        data-show-errors="false"
        class="api_football_loader">
    </div>
    <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """
    components.html(widget_html, height=1000, scrolling=True)
