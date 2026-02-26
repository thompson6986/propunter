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
st.set_page_config(page_title="Pro Punter V68", page_icon="🛡️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .slip-card { border: 1px solid #30363d; padding: 15px; border-radius: 10px; margin-bottom: 15px; background: #161b22; }
    .timer-badge { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
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

# --- QUOTA SAVER: CACHING ODDS ---
@st.cache_data(ttl=600) # Odds worden nu 10 minuten onthouden!
def get_safe_odds(f_id):
    try:
        res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
        return res.json()
    except: return {}

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 GENERATOR", "📡 TRACKER", "🏟️ STADIUM"])

with t1:
    st.markdown(f"💰 Saldo: **€{st.session_state.get('balance', 100):.2f}**")
    u_id = st.text_input("User ID", value="punter_01")
    
    if st.button("🚀 SMART SCAN (BESPAAR CREDITS)", use_container_width=True):
        try:
            with st.spinner("Systeem optimaliseert dataverbruik..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                # We halen minder fixtures op om odds-calls te minimaliseren
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS', 'next': 20}) 
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response']:
                        f_id = f['fixture']['id']
                        f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                        
                        o_data = get_safe_odds(f_id)
                        if o_data.get('response') and len(o_data['response']) > 0:
                            for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                                # Strikte marktselectie (Win FT, O/U, BTTS)
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
                    
                    if len(pool) >= 2:
                        st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(3)]
                    else: st.warning("Te weinig data voor jouw filters op dit moment.")
        except: st.error("API limiet bereikt.")

    # VEILIGE WEERGAVE (Crash-proof)
    if 'gen_slips' in st.session_state:
        for i, slip in enumerate(st.session_state.gen_slips):
            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
            t_o = 1.0
            for m in slip:
                t_o *= m.get('odd', 1.0)
                # Gebruik .get() om KeyErrors te voorkomen!
                s_t = m.get('start_time', 'Live')
                st.write(f"🕒 {s_t} | **{m.get('match', 'Match')}** | {m.get('market', 'Market')} (@{m.get('odd', 1.0)})")
            
            if st.button(f"✅ PLAATS SLIP @{round(t_o, 2)}", key=f"p_{i}"):
                if db:
                    db.collection("saved_slips").add({
                        "user_id": u_id, "timestamp": datetime.now(TIMEZONE),
                        "total_odd": round(t_o, 2), "matches": slip, "stake": 10.0
                    })
                    st.success("Succes!"); time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown("### 📡 Live Tracker")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).get()
        if docs:
            all_ids = []
            for d in docs:
                for m in d.to_dict().get('matches', []): all_ids.append(str(m.get('fixture_id')))
            
            if all_ids:
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(set(all_ids))})
                live_map = {f['fixture']['id']: f for f in res.json().get('response', [])} if res.status_code == 200 else {}

                for doc in docs:
                    s = doc.to_dict(); s['id'] = doc.id
                    st.markdown(f'<div class="slip-card" style="border-left: 4px solid #3fb950;"><b>Slip @{s.get("total_odd")}</b>', unsafe_allow_html=True)
                    for m in s.get('matches', []):
                        f_info = live_map.get(m.get('fixture_id'))
                        score = f"{f_info['goals']['home']} - {f_info['goals']['away']}" if f_info else "0 - 0"
                        status = f_info['fixture']['status']['short'] if f_info else "NS"
                        timer = f"🔴 {f_info['fixture']['status']['elapsed']}'" if status in ['1H', '2H', 'HT'] else f"🕒 {m.get('start_time', 'NS')}"
                        st.write(f"{timer} | {m.get('match')}: **{score}**")
                    if st.button("🗑️", key=f"d_{s['id']}"):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

with t3:
    # WIDGET GEBRUIKT GEEN CREDITS! Ideaal voor live volgen.
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
