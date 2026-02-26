import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

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
    .stake-text { color: #58a6ff; font-weight: bold; }
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
if 'gen_slips' not in st.session_state: st.session_state.gen_slips = []
if 'balance' not in st.session_state: st.session_state.balance = 1000.0 # Startkapitaal

t1, t2 = st.tabs(["🚀 SLIP GENERATOR", "📡 LIVE TRACKER & PORTFOLIO"])

# --- TAB 1: GENERATOR ---
with t1:
    st.markdown(f"### 🚀 Generator | 💰 Bankroll: **€{st.session_state.balance:.2f}**")
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        m_count = c1.slider("Aantal matchen", 1, 5, 2)
        min_o = c2.number_input("Min Odd", value=1.50)
        max_o = c3.number_input("Max Odd", value=5.00)
        window = c4.selectbox("Tijdvenster", ["2 uur", "6 uur", "Vandaag"])
        
        f1, f2, f3, f4 = st.columns(4)
        m_1x2 = f1.checkbox("1X2", value=True)
        m_dc = f2.checkbox("Double Chance", value=True)
        m_ou = f3.checkbox("Over/Under", value=True)
        m_btts = f4.checkbox("BTTS", value=True)
        u_id = st.text_input("User ID", value="punter_01")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 ZOEK BEREKENDE WEDDENSCHAPPEN", use_container_width=True):
        try:
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
            data = res.json()
            if data.get('response'):
                now_ts = int(time.time())
                limit_h = {"2 uur": 2, "6 uur": 6, "Vandaag": 24}[window]
                pool = []
                for f in data['response']:
                    ts = f['fixture']['timestamp']
                    if 0.01 <= (ts - now_ts)/3600 <= limit_h:
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f['fixture']['id']})
                        o_data = o_res.json()
                        if o_data.get('response'):
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    allowed = (bet['name'] == "Match Winner" and m_1x2) or \
                                              (bet['name'] == "Double Chance" and m_dc) or \
                                              ("Over/Under" in bet['name'] and m_ou) or \
                                              (bet['name'] == "Both Teams Score" and m_btts)
                                    if allowed:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            if min_o <= odd <= max_o:
                                                pool.append({"fixture_id": f['fixture']['id'], "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": f"{bet['name']}: {val['value']}", "odd": odd, "prob": round((1/odd)*100+4.5, 1), "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')})
                pool.sort(key=lambda x: x['prob'], reverse=True)
                st.session_state.gen_slips = [pool[i:i + m_count] for i in range(0, len(pool), m_count)]
        except: st.error("Data ophalen mislukt.")

    for i, slip in enumerate(st.session_state.gen_slips[:4]):
        if len(slip) == m_count:
            st.markdown('<div class="slip-container">', unsafe_allow_html=True)
            t_odd = 1.0
            for m in slip:
                t_odd *= m['odd']
                st.markdown(f'<div class="match-row"><div><span class="prob-badge">{m["prob"]}%</span><div class="team-text">{m["match"]}</div><div style="color:#8b949e; font-size:0.85rem;">🕒 {m["time"]} | {m["market"]}</div></div><div class="score-badge">@{m["odd"]}</div></div>', unsafe_allow_html=True)
            
            t_odd = round(t_odd, 2)
            st.write(f"**Totaal Odds: @{t_odd}**")
            
            # --- STAKE INPUT ---
            col_a, col_b = st.columns([2, 1])
            stake = col_a.number_input(f"Inzet voor Slip {i+1} (€)", min_value=1.0, max_value=float(st.session_state.balance), value=10.0, key=f"stake_{i}")
            
            if col_b.button(f"💾 PLAATS BET", key=f"place_{i}", use_container_width=True):
                if st.session_state.balance >= stake:
                    st.session_state.balance -= stake # Trek af van saldo
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": u_id, 
                            "timestamp": datetime.now(TIMEZONE), 
                            "total_odd": t_odd, 
                            "matches": slip, 
                            "stake": stake,
                            "potential_payout": round(stake * t_odd, 2)
                        })
                        st.success(f"Bet geplaatst! Nieuw saldo: €{st.session_state.balance:.2f}")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Onvoldoende saldo!")
            st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: TRACKER ---
with t2:
    st.markdown(f"### 📡 Portfolio | Saldo: €{st.session_state.balance:.2f}")
    if db:
        try:
            saved = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
            if saved:
                f_ids = [m['fixture_id'] for d in saved for m in d.to_dict()['matches']]
                live_data = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []): live_data[f['fixture']['id']] = f

                for d in saved:
                    s = d.to_dict(); s['id'] = d.id
                    st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                    st.markdown(f"**Slip @{s['total_odd']}** | Inzet: <span class='stake-text'>€{s['stake']}</span> | Potentiële Winst: <span style='color:#3fb950'>€{s['potential_payout']}</span>", unsafe_allow_html=True)
                    
                    win_count = 0
                    for m in s['matches']:
                        f_upd = live_data.get(m['fixture_id'])
                        h_g = f_upd['goals']['home'] if f_upd and f_upd['goals']['home'] is not None else 0
                        a_g = f_upd['goals']['away'] if f_upd and f_upd['goals']['away'] is not None else 0
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        st.markdown(f'<div><div class="team-text">{m["match"]}</div><div style="color:#8b949e;">{m["market"]} (@{m["odd"]})</div></div>', unsafe_allow_html=True)
                        if f_upd:
                            stat = f_upd['fixture']['status']['short']
                            if stat in ['1H', '2H', 'HT']:
                                st.markdown(f'<div><div class="live-indicator">🔴 {f_upd["fixture"]["status"]["elapsed"]}\'</div>', unsafe_allow_html=True)
                            elif stat == 'FT':
                                win_count += 1
                                st.markdown('<div>🏁 FT', unsafe_allow_html=True)
                            else: st.markdown(f'<div>🕒 {m["time"]}', unsafe_allow_html=True)
                        st.markdown(f'<div class="score-badge">{h_g} - {a_g}</div></div></div>', unsafe_allow_html=True)
                    
                    # CASH OUT BEREKENING
                    c_val = round((s['stake'] * s['total_odd']) * (win_count / len(s['matches'])) * 0.88, 2)
                    cc1, cc2 = st.columns([3, 1])
                    if win_count > 0:
                        if cc1.button(f"💰 CASH OUT €{max(c_val, 1.0)}", key=f"co_{s['id']}", use_container_width=True):
                            st.session_state.balance += max(c_val, 1.0)
                            db.collection("saved_slips").document(s['id']).delete()
                            st.rerun()
                    if cc2.button("🗑️ Verlies nemen", key=f"del_{s['id']}", use_container_width=True):
                        db.collection("saved_slips").document(s['id']).delete()
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else: st.info("Geen actieve weddenschappen.")
        except Exception as e: st.warning("Wachten op database...")
