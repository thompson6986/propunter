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
st.set_page_config(page_title="Pro Punter V67 - Quota Saver", page_icon="🛡️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

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

# --- QUOTA OPTIMIZATION: CACHING ---
@st.cache_data(ttl=300) # Cache odds voor 5 minuten om credits te sparen
def get_odds_cached(fixture_id):
    res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': fixture_id, 'bookmaker': 6}) # Bwin (6) als standaard voor snelheid
    return res.json()

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 GENERATOR", "📡 TRACKER", "🏟️ STADIUM"])

with t1:
    st.markdown(f"💰 Saldo: **€{st.session_state.get('balance', 100):.2f}**")
    u_id = st.text_input("User ID", value="punter_01")
    
    if st.button("🚀 GENEREER SLIPS (SMART SCAN)", use_container_width=True):
        try:
            with st.spinner("Slim scannen (credits besparen)..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                # Haal enkel de belangrijkste competities op om calls te beperken
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS', 'next': 30}) 
                data = res.json()
                
                if data.get('response'):
                    pool = []
                    for f in data['response']:
                        f_id = f['fixture']['id']
                        f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
                        
                        # Gebruik de gecachte odds functie
                        o_data = get_odds_cached(f_id)
                        if o_data.get('response'):
                            for bet in o_data['response'][0]['bookmakers'][0]['bets']:
                                if bet['name'] in ["Match Winner", "Both Teams Score", "Goals Over/Under"]:
                                    for val in bet['values']:
                                        if any(x in str(val['value']) for x in ["Asian", "Corner", "3.5", "4.5"]): continue
                                        pool.append({
                                            "fixture_id": f_id, "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                            "market": f"{bet['name']}: {val['value']}", "odd": float(val['odd']), "start_time": f_time
                                        })
                    
                    if pool:
                        st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(4)]
        except: st.error("API limiet bijna bereikt. Wacht even.")

    # Voorstel Slips weergave...
    for i, slip in enumerate(st.session_state.get('gen_slips', [])):
        with st.container():
            st.markdown('<div style="border:1px solid #30363d; padding:15px; border-radius:10px; margin-bottom:10px;">', unsafe_allow_html=True)
            t_o = 1.0
            for m in slip:
                t_o *= m['odd']
                st.write(f"🕒 {m['start_time']} | **{m['match']}** | {m['market']} (@{m['odd']})")
            
            if st.button(f"✅ PLAATS @{round(t_o, 2)}", key=f"p_{i}"):
                if db:
                    db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": round(t_o, 2), "matches": slip, "stake": 10.0})
                    st.success("Opgeslagen!")
            st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown("### 📡 Live Tracker (Smart Refresh)")
    # Tracker haalt nu alle data in 1 call op (bespaart enorm veel credits)
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        if docs:
            all_ids = []
            for d in docs:
                for m in d.to_dict().get('matches', []): all_ids.append(str(m['fixture_id']))
            
            if all_ids:
                # 1 CALL voor alle fixtures in je portfolio!
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(set(all_ids))})
                live_map = {f['fixture']['id']: f for f in res.json().get('response', [])} if res.status_code == 200 else {}

                for doc in docs:
                    s = doc.to_dict(); s['id'] = doc.id
                    st.info(f"Slip @{s.get('total_odd')} | Inzet: €{s.get('stake', 10)}")
                    for m in s.get('matches', []):
                        f_info = live_map.get(m['fixture_id'])
                        score = f"{f_info['goals']['home']} - {f_info['goals']['away']}" if f_info else "0 - 0"
                        status = f_info['fixture']['status']['short'] if f_info else "NS"
                        time_label = f"🔴 {f_info['fixture']['status']['elapsed']}'" if status in ['1H', '2H', 'HT'] else f"🕒 {m.get('start_time', 'NS')}"
                        st.write(f"{time_label} | **{m['match']}**: {score} ({m['market']})")
                    if st.button("🗑️", key=f"d_{s['id']}"):
                        db.collection("saved_slips").document(s['id']).delete(); st.rerun()

with t3:
    # De WIDGET is GRATIS (kost GEEN credits van je API-key voor data-updates)
    # Gebruik deze tab om live te volgen, dat bespaart je credits!
    components.html(f"""
        <div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div>
        <script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>
    """, height=1000, scrolling=True)
