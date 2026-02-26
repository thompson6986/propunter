import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG & STYLING (Vastgehouden design) ---
st.set_page_config(page_title="Professional Parlay Builder", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; font-weight: bold; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-card { background-color: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #238636; }
    .prob-tag { color: #3fb950; font-weight: bold; font-size: 1.2rem; }
    .team-row { font-size: 1.1rem; font-weight: 600; color: #adbac7; margin: 10px 0; }
    .odd-badge { background: #21262d; padding: 8px 15px; border-radius: 6px; border: 1px solid #30363d; font-weight: bold; color: #58a6ff; font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- DB & API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# Initialiseer Firebase (voor opslag)
if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- STATE ---
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = []

# --- TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📁 Mijn Opgeslagen Slips"])

with t1:
    st.title("📈 Pro Parlay Builder")
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        user_id = st.text_input("User ID (voor opslag)", value="punter_01")
        c1, c2, c3 = st.columns(3)
        match_count = c1.slider("Unieke Matchen / Slip", 1, 5, 2)
        min_odd_val = c2.number_input("Min. Odd / Match", value=1.20)
        max_odd_val = c3.number_input("Max. Odd / Match", value=2.50)
        
        m1, m2, m3, m4 = st.columns(4)
        allow_winner = m1.checkbox("1X2", value=True)
        allow_dc = m2.checkbox("Double Chance", value=True)
        allow_ou = m3.checkbox("Over/Under", value=True)
        allow_btts = m4.checkbox("BTTS", value=False)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER SLIPS"):
        try:
            with st.spinner("Scannen..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                fix_data = fix_res.json()

                if fix_data.get('response'):
                    now_ts = int(time.time())
                    match_pool = []
                    for f in fix_data['response']:
                        ts = f['fixture']['timestamp']
                        if 0.01 <= (ts - now_ts)/3600 <= 6: 
                            f_id = f['fixture']['id']
                            odd_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                            o_data = odd_res.json()
                            if o_data.get('response'):
                                best_bet = None
                                max_p = 0
                                for bm in o_data['response'][0]['bookmakers']:
                                    for bet in bm['bets']:
                                        b_name = bet['name']
                                        is_allowed = (b_name == "Match Winner" and allow_winner) or \
                                                     (b_name == "Double Chance" and allow_dc) or \
                                                     (b_name == "Goals Over/Under" and allow_ou) or \
                                                     (b_name == "Both Teams Score" and allow_btts)
                                        if is_allowed:
                                            for val in bet['values']:
                                                if any(x in val['value'] for x in ["Asian", "Half"]): continue
                                                odd = float(val['odd'])
                                                prob = round((1/odd) * 100 + 4.5, 1)
                                                if min_odd_val <= odd <= max_odd_val and prob > max_p:
                                                    max_p = prob
                                                    best_bet = {"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                                "market": f"{b_name}: {val['value']}", "odd": odd, "prob": prob, 
                                                                "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')}
                                if best_bet: match_pool.append(best_bet)
                    
                    match_pool.sort(key=lambda x: x['prob'], reverse=True)
                    st.session_state.generated_slips = [match_pool[i:i + match_count] for i in range(0, len(match_pool), match_count)]
        except Exception as e: st.error(f"Fout: {e}")

    if st.session_state.generated_slips:
        for i, slip in enumerate(st.session_state.generated_slips[:5]):
            if len(slip) == match_count:
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                t_odd = 1.0
                for m in slip:
                    t_odd *= m['odd']
                    st.markdown(f"<span class='prob-tag'>{m['prob']}%</span> <span class='team-row'>{m['match']}</span>", unsafe_allow_html=True)
                    st.caption(f"{m['time']} | {m['market']} | @{m['odd']}")
                
                final_odd = round(t_odd, 2)
                st.markdown(f"**Totaal: @{final_odd}**")
                
                if st.button(f"💾 Sla Slip {i+1} op", key=f"save_{i}"):
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": user_id,
                            "timestamp": datetime.now(TIMEZONE),
                            "total_odd": final_odd,
                            "matches": slip,
                            "status": "Open"
                        })
                        st.success("Opgeslagen!")
                st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.header("📁 Jouw Portfolio")
    if db:
        saved = db.collection("saved_slips").where("user_id", "==", user_id).order_by("timestamp", direction="DESCENDING").limit(10).get()
        if not saved: st.info("Nog geen slips opgeslagen.")
        for doc in saved:
            s = doc.to_dict()
            with st.expander(f"📅 {s['timestamp'].strftime('%d/%m %H:%M')} | Odds: @{s['total_odd']} | Status: {s['status']}"):
                for m in s['matches']:
                    st.write(f"✅ {m['match']} - {m['market']} (@{m['odd']})")
                if st.button("🗑️ Verwijder", key=f"del_{doc.id}"):
                    db.collection("saved_slips").document(doc.id).delete()
                    st.rerun()
