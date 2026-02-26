import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Dashboard", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-container { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-top: 4px solid #238636; }
    .match-row { background-color: #1c2128; border-radius: 8px; padding: 12px; margin: 8px 0; border: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
    .prob-badge { background-color: #23863622; color: #3fb950; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; border: 1px solid #238636; }
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
if 'gen_slips' not in st.session_state: st.session_state.gen_slips = []
if 'balance' not in st.session_state: st.session_state.balance = 100.0

t1, t2 = st.tabs(["🚀 SLIP GENERATOR", "📡 LIVE TRACKER & PORTFOLIO"])

# --- TAB 1: GENERATOR ---
with t1:
    st.markdown(f"### 🚀 Generator | 💰 Saldo: **€{st.session_state.balance:.2f}**")
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        target_odd_cat = c1.selectbox("Doel Odds Totaal", [1.5, 2.0, 3.0, 5.0])
        m_count = c2.slider("Matchen per Slip", 1, 5, 2)
        u_id = st.text_input("User ID", value="punter_01")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER PROFESSIONELE SLIPS", use_container_width=True):
        try:
            with st.spinner("Data analyseren..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                data = res.json()
                if data.get('response'):
                    pool = []
                    # We scannen de eerste 50 matchen voor variatie
                    for f in data['response'][:50]:
                        f_id = f['fixture']['id']
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                        o_data = o_res.json()
                        if o_data.get('response'):
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    if bet['name'] in ["Match Winner", "Double Chance", "Goals Over/Under"]:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            if 1.20 <= odd <= 3.50:
                                                pool.append({
                                                    "fixture_id": f_id,
                                                    "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                                    "market": f"{bet['name']}: {val['value']}",
                                                    "odd": odd,
                                                    "prob": round((1/odd)*100+4, 1),
                                                    "time": datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                                                })
                    
                    # Bouw slips
                    valid_slips = []
                    for _ in range(10): # Probeer 10 combinaties
                        if len(pool) >= m_count:
                            candidate = random.sample(pool, m_count)
                            total_o = 1.0
                            for m in candidate: total_o *= m['odd']
                            if (target_odd_cat * 0.7) <= total_o <= (target_odd_cat * 1.6):
                                valid_slips.append(candidate)
                    
                    st.session_state.gen_slips = valid_slips if valid_slips else [random.sample(pool, m_count)]
        except: st.error("API error of geen data beschikbaar.")

    for i, slip in enumerate(st.session_state.gen_slips[:4]):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            st.markdown(f'<div class="match-row"><div><span class="prob-badge">{m["prob"]}%</span><div style="color:#c9d1d9; font-weight:bold;">{m["match"]}</div><div style="color:#8b949e; font-size:0.85rem;">🕒 {m["time"]} | {m["market"]}</div></div><div class="score-badge">@{m["odd"]}</div></div>', unsafe_allow_html=True)
        
        t_odd = round(t_odd, 2)
        c_a, c_b = st.columns([2, 1])
        stake = c_a.number_input(f"Inzet (€)", 1.0, float(st.session_state.balance), 10.0, key=f"s_{i}")
        if c_b.button(f"💾 PLAATS @{t_odd}", key=f"p_{i}", use_container_width=True):
            if st.session_state.balance >= stake:
                st.session_state.balance -= stake
                if db:
                    db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": t_odd, "matches": slip, "stake": stake})
                    st.toast("Bet geplaatst!")
                    time.sleep(1); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: TRACKER ---
with t2:
    st.markdown(f"### 📡 Portfolio | Saldo: €{st.session_state.balance:.2f}")
    if db:
        try:
            docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
            if docs:
                # Verzamel IDs voor live updates
                f_ids = list(set([m['fixture_id'] for d in docs for m in d.to_dict()['matches']]))
                live_map = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, f_ids))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []): live_map[f['fixture']['id']] = f

                for doc in docs:
                    s = doc.to_dict(); s['id'] = doc.id
                    st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                    st.markdown(f"**Slip @{s['total_odd']}** | Inzet: €{s['stake']}", unsafe_allow_html=True)
                    
                    win_count = 0
                    for m in s['matches']:
                        f_upd = live_map.get(m['fixture_id'])
                        h_g = f_upd['goals']['home'] if f_upd and f_upd['goals']['home'] is not None else 0
                        a_g = f_upd['goals']['away'] if f_upd and f_upd['goals']['away'] is not None else 0
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        st.markdown(f'<div><div style="color:#c9d1d9; font-weight:bold;">{m["match"]}</div><div style="color:#8b949e;">{m["market"]} (@{m["odd"]})</div></div>', unsafe_allow_html=True)
                        if f_upd:
                            stat = f_upd['fixture']['status']['short']
                            if stat in ['1H', '2H', 'HT']:
                                st.markdown(f'<div><div class="live-indicator">🔴 {f_upd["fixture"]["status"]["elapsed"]}\'</div>', unsafe_allow_html=True)
                            elif stat == 'FT':
                                win_count += 1
                                st.markdown('<div>🏁 FT', unsafe_allow_html=True)
                        st.markdown(f'<div class="score-badge">{h_g} - {a_g}</div></div></div>', unsafe_allow_html=True)
                    
                    # Cash out
                    co1, co2 = st.columns([3, 1])
                    c_val = round((s['stake'] * s['total_odd']) * (win_count / len(s['matches'])) * 0.85, 2)
                    if win_count > 0:
                        if co1.button(f"💰 CASH OUT €{max(c_val, 1.0)}", key=f"co_{s['id']}", use_container_width=True):
                            st.session_state.balance += max(c_val, 1.0)
                            db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    if co2.button("🗑️", key=f"del_{s['id']}", use_container_width=True):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else: st.info("Geen actieve slips.")
        except: st.warning("Database wordt gesynchroniseerd...")
