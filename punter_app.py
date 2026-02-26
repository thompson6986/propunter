import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Suite", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; font-weight: bold; height: 3em; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-container { background-color: #0d1117; border: 2px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 30px; }
    .match-row { background-color: #161b22; border-radius: 8px; padding: 15px; margin: 10px 0; border: 1px solid #21262d; }
    .prob-tag { color: #3fb950; font-weight: bold; font-size: 1.1rem; }
    .live-timer { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
    .score-box { background: #000; color: #fff; padding: 5px 15px; border-radius: 5px; font-family: monospace; font-size: 1.3rem; font-weight: bold; border: 1px solid #58a6ff; }
    @keyframes blinker { 50% { opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

# --- DB & API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- SESSION STATE ---
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = []

# --- TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Live Tracker Dashboard"])

# --- TAB 1: GENERATOR ---
with t1:
    st.title("🚀 Professional Parlay Generator")
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        match_per_slip = c1.slider("Matchen per Slip", 1, 5, 2)
        min_odd = c2.number_input("Min. Odd / Match", value=1.20)
        max_odd = c3.number_input("Max. Odd / Match", value=2.50)
        time_frame = c4.selectbox("Tijdvenster", ["2 uur", "6 uur", "Vandaag"])

        m1, m2, m3, m4 = st.columns(4)
        allow_1x2 = m1.checkbox("1X2", value=True)
        allow_dc = m2.checkbox("Double Chance", value=True)
        allow_ou = m3.checkbox("Over/Under", value=True)
        allow_btts = m4.checkbox("BTTS", value=False)
        
        min_prob = st.slider("Minimale Kans (%)", 30, 95, 60)
        user_id = st.text_input("User ID", value="punter_01")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER SLIPS"):
        try:
            with st.spinner("Markten analyseren..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                fix_data = fix_res.json()

                if fix_data.get('response'):
                    now_ts = int(time.time())
                    limit_h = {"2 uur": 2, "6 uur": 6, "Vandaag": 24}[time_frame]
                    
                    pool = []
                    for f in fix_data['response']:
                        ts = f['fixture']['timestamp']
                        if 0.01 <= (ts - now_ts)/3600 <= limit_h:
                            f_id = f['fixture']['id']
                            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                            o_data = o_res.json()
                            if o_data.get('response'):
                                best_bet = None
                                max_p = 0
                                for bm in o_data['response'][0]['bookmakers']:
                                    for bet in bm['bets']:
                                        b_name = bet['name']
                                        if (b_name == "Match Winner" and allow_1x2) or \
                                           (b_name == "Double Chance" and allow_dc) or \
                                           ("Over/Under" in b_name and allow_ou) or \
                                           (b_name == "Both Teams Score" and allow_btts):
                                            for val in bet['values']:
                                                if any(x in val['value'] for x in ["Asian", "Half"]): continue
                                                odd = float(val['odd'])
                                                prob = round((1/odd)*100 + 4.5, 1)
                                                if min_odd <= odd <= max_odd and prob >= min_prob:
                                                    if prob > max_p:
                                                        max_p = prob
                                                        best_bet = {"fixture_id": f_id, "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                                    "market": f"{b_name}: {val['value']}", "odd": odd, "prob": prob, 
                                                                    "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')}
                                if best_bet: pool.append(best_bet)
                    pool.sort(key=lambda x: x['prob'], reverse=True)
                    st.session_state.generated_slips = [pool[i:i + match_per_slip] for i in range(0, len(pool), match_per_slip)]
        except Exception as e: st.error(f"Fout: {e}")

    for i, slip in enumerate(st.session_state.generated_slips[:8]):
        if len(slip) == match_per_slip:
            st.markdown('<div class="slip-container">', unsafe_allow_html=True)
            total_o = 1.0
            for m in slip:
                total_o *= m['odd']
                st.markdown(f"<span class='prob-tag'>{m['prob']}%</span> **{m['match']}**")
                st.caption(f"{m['time']} | {m['market']} | @{m['odd']}")
            st.write(f"**Totaal Odds: @{round(total_o, 2)}**")
            if st.button(f"💾 Sla Slip {i+1} op", key=f"save_{i}"):
                if db:
                    db.collection("saved_slips").add({"user_id": user_id, "timestamp": datetime.now(TIMEZONE), "total_odd": round(total_o, 2), "matches": slip})
                    st.success("Opgeslagen!")
            st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER ---
with t2:
    st.title("📡 Live Tracker")
    if db:
        try:
            saved = (db.collection("saved_slips").where("user_id", "==", user_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get())
            if saved:
                f_ids = []
                docs = []
                for d in saved:
                    data = d.to_dict(); data['id'] = d.id; docs.append(data)
                    for m in data['matches']: f_ids.append(m['fixture_id'])
                
                live_data = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []): live_data[f['fixture']['id']] = f

                for s in docs:
                    st.markdown('<div class="slip-container">', unsafe_allow_html=True)
                    st.subheader(f"Slip @{s['total_odd']}")
                    win_count = 0
                    for m in s['matches']:
                        f_id = m['fixture_id']
                        f_upd = live_data.get(f_id)
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"**{m['match']}**\n\n{m['market']} (@{m['odd']})")
                        if f_upd:
                            status = f_upd['fixture']['status']['short']
                            score = f"{f_upd['goals']['home']} - {f_upd['goals']['away']}"
                            if status in ['1H', '2H', 'HT']:
                                c2.markdown(f"<span class='live-timer'>🔴 {f_upd['fixture']['status']['elapsed']}'</span>", unsafe_allow_html=True)
                            elif status == 'FT':
                                win_count += 1
                                c2.write("🏁 FT")
                            else:
                                c2.write(f"🕒 {m['time']}")
                            c2.markdown(f"<div class='score-box'>{score}</div>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    if st.button("🗑️ Verwijder", key=f"del_{s['id']}"):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else: st.info("Geen actieve slips.")
        except: st.warning("Index wordt aangemaakt...")
