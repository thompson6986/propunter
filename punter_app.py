import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore
import random

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter V70", page_icon="🛡️", layout="wide")
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

# --- REPAIR TOOL: CACHE CLEAR ---
def reset_generator():
    st.cache_data.clear()
    st.session_state.gen_slips = []
    st.toast("Generator gereset en cache geleegd!")

# --- SMART SCAN (MET ERROR HANDLING) ---
@st.cache_data(ttl=600, show_spinner=False)
def fetch_smart_pool(today_date):
    try:
        # Stap 1: Haal fixtures op (Laag verbruik: 1 credit)
        res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today_date, 'status': 'NS', 'next': 15})
        data = res.json()
        
        if not data.get('response'):
            return {"error": "Geen wedstrijden gevonden of API limiet bereikt."}
            
        pool = []
        for f in data['response']:
            f_id = f['fixture']['id']
            f_time = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')
            
            # Stap 2: Haal odds op (Hoog verbruik: 1 credit per match)
            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
            o_data = o_res.json()
            
            if o_data.get('response') and len(o_data['response']) > 0:
                for bet in o_data['response'][0]['bookmakers'][0]['bets']:
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
        return {"pool": pool}
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
t1, t2, t3 = st.tabs(["🚀 GENERATOR", "📡 TRACKER", "🏟️ STADIUM"])

with t1:
    c_top1, c_top2 = st.columns([3, 1])
    c_top1.markdown(f"### 🚀 Generator | Saldo: €{st.session_state.get('balance', 100):.2f}")
    if c_top2.button("🧹 Reset Cache"): reset_generator()
    
    u_id = st.text_input("User ID", value="punter_01")

    if st.button("🚀 GENEREER NIEUWE VOORSTELLEN", use_container_width=True):
        today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        result = fetch_smart_pool(today)
        
        if "error" in result:
            st.error(f"🚨 Generator gestopt: {result['error']}")
            st.info("Waarschijnlijk zijn je 1000 gratis credits voor vandaag op. Gebruik de Stadium-tab om live te volgen.")
        else:
            pool = result["pool"]
            if len(pool) >= 2:
                st.session_state.gen_slips = [random.sample(pool, 2) for _ in range(3)]
                st.success(f"Scan voltooid! {len(pool)} opties gevonden.")
            else:
                st.warning("Niet genoeg wedstrijden gevonden met jouw filters.")

    # Weergave slips (met extra check)
    if st.session_state.get('gen_slips'):
        for i, slip in enumerate(st.session_state.gen_slips):
            st.markdown('<div style="border:1px solid #30363d; padding:15px; border-radius:10px; margin-bottom:10px; background:#161b22;">', unsafe_allow_html=True)
            total_odd = 1.0
            for m in slip:
                total_odd *= m['odd']
                st.write(f"🕒 {m.get('start_time')} | **{m['match']}** | {m['market']} (@{m['odd']})")
            
            if st.button(f"✅ PLAATS @{round(total_odd, 2)}", key=f"place_{i}"):
                if db:
                    db.collection("saved_slips").add({"user_id": u_id, "timestamp": datetime.now(TIMEZONE), "total_odd": round(total_odd, 2), "matches": slip, "stake": 10.0})
                    st.toast("Bet geplaatst!"); time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# [Tab 2 & 3 blijven gelijk aan V69]
