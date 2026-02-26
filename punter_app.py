import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Live Suite", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; font-weight: bold; height: 3em; }
    .slip-container { background-color: #0d1117; border: 2px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 30px; }
    .match-row { background-color: #161b22; border-radius: 8px; padding: 15px; margin: 10px 0; border: 1px solid #21262d; }
    .live-timer { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
    .score-box { background: #000; color: #fff; padding: 8px 15px; border-radius: 5px; font-family: monospace; font-size: 1.4rem; font-weight: bold; border: 1px solid #58a6ff; }
    .status-won { color: #3fb950; font-weight: bold; }
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

t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Live Tracker Dashboard"])

# --- TAB 1: GENERATOR ---
with t1:
    st.title("🚀 Professional Parlay Generator")
    with st.container():
        st.markdown('<div class="control-panel" style="background-color: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 20px;">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        m_per_slip = c1.slider("Matchen per Slip", 1, 5, 2)
        min_o = c2.number_input("Min. Odd", value=1.20)
        max_o = c3.number_input("Max. Odd", value=2.50)
        t_frame = c4.selectbox("Venster", ["2 uur", "6 uur", "Vandaag"])
        
        user_id = st.text_input("User ID", value="punter_01")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER SLIPS"):
        try:
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
            data = fix_res.json()
            if data.get('response'):
                now_ts = int(time.time())
                limit = {"2 uur": 2, "6 uur": 6, "Vandaag": 24}[t_frame]
                pool = []
                for f in data['response']:
                    ts = f['fixture']['timestamp']
                    if 0.01 <= (ts - now_ts)/3600 <= limit:
                        f_id = f['fixture']['id']
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                        o_data = o_res.json()
                        if o_data.get('response'):
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    if bet['name'] in ["Match Winner", "Double Chance"]:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            prob = round((1/odd)*100 + 4.5, 1)
                                            if min_o <= odd <= max_o:
                                                pool.append({
                                                    "fixture_id": f_id, "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                    "market": f"{bet['name']}: {val['value']}", "odd": odd, "prob": prob, 
                                                    "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')
                                                })
                pool.sort(key=lambda x: x['prob'], reverse=True)
                st.session_state.generated_slips = [pool[i:i + m_per_slip] for i in range(0, len(pool), m_per_slip)]
        except: st.error("Fout bij ophalen data.")

    for i, slip in enumerate(st.session_state.generated_slips[:5]):
        st.markdown('<div class="slip-container">', unsafe_allow_html=True)
        t_odd = 1.0
        for m in slip:
            t_odd *= m['odd']
            st.write(f"**{m['prob']}%** {m['match']} ({m['market']}) @{m['odd']}")
        if st.button(f"💾 Sla Slip {i+1} op", key=f"gen_{i}"):
            if db:
                db.collection("saved_slips").add({"user_id": user_id, "timestamp": datetime.now(TIMEZONE), "total_odd": round(t_odd, 2), "matches": slip})
                st.success("Opgeslagen!")
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER ---
with t2:
    st.title("📡 Live Tracker Dashboard")
    if db:
        try:
            saved = (db.collection("saved_slips").where("user_id", "==", user_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get())
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
                    st.subheader(f"Slip @{s['total_odd']}")
                    
                    win_count = 0
                    for m in s['matches']:
                        f_id = m['fixture_id']
                        f_upd = live_data.get(f_id)
                        
                        st.markdown('<div class="match-row">', unsafe_allow_html=True)
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"**{m['match']}**\n\n{m['market']} (@{m['odd']})")
                        
                        # --- FIX: GEEN 'NONE' MEER ---
                        h_g = f_upd['goals']['home'] if f_upd and f_upd['goals']['home'] is not None else 0
                        a_g = f_upd['goals']['away'] if f_upd and f_upd['goals']['away'] is not None else 0
                        score = f"{h_g} - {a_g}"
                        
                        if f_upd:
                            stat = f_upd['fixture']['status']['short']
                            if stat in ['1H', '2H', 'HT']:
                                c2.markdown(f"<span class='live-timer'>🔴 {f_upd['fixture']['status']['elapsed']}'</span>", unsafe_allow_html=True)
                            elif stat == 'FT':
                                win_count += 1
                                c2.write("🏁 FT")
                            else:
                                c2.write(f"🕒 {m['time']}")
                        c2.markdown(f"<div class='score-box'>{score}</div>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # CASH-OUT LOGICA
                    if win_count > 0:
                        cash = round((10 * s['total_odd']) * (win_count / len(s['matches'])) * 0.82, 2)
                        st.success(f"💰 Cash-out: €{max(cash, 1.0)}")
                    
                    if st.button("🗑️ Verwijder", key=f"del_{s['id']}"):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        except: st.warning("Index wordt geladen...")
