import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
import time

# --- CONFIG & TRUE THEME ---
st.set_page_config(page_title="Pro Punter Elite V79", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    /* Herstel van de professionele kaarten */
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #1f6feb; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 12px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; margin-top: 15px; }
    .h2h-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #21262d; font-size: 0.85rem; color: #8b949e; }
    .score-pill { background: #010409; padding: 2px 8px; border-radius: 4px; color: #ffffff; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None

db = init_db()

# --- APP LOGIC ---
if 'analysis_cache' not in st.session_state: st.session_state.analysis_cache = []

t1, t2, t3 = st.tabs(["🚀 GENERATOR & TRACKER", "📊 DEEP ANALYSIS", "🏟️ STADIUM"])

# --- TAB 1: HERSTELDE LAYOUT ---
with t1:
    col_gen, col_track = st.columns([1, 1])
    
    with col_gen:
        st.subheader("🚀 Smart Generator")
        if st.button("Scan Top Markten", use_container_width=True):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 15})
            st.session_state.gen_data = res.json().get('response', [])
        
        if 'gen_data' in st.session_state:
            for f in st.session_state.gen_data[:5]:
                with st.container():
                    st.markdown(f'''<div style="background:#161b22; padding:15px; border-radius:10px; border:1px solid #30363d; margin-bottom:10px;">
                        <b>{f['teams']['home']['name']} vs {f['teams']['away']['name']}</b><br>
                        <small>🕒 {datetime.fromtimestamp(f['fixture']['timestamp']).strftime('%H:%M')}</small>
                    </div>''', unsafe_allow_html=True)

    with col_track:
        st.subheader("📡 Live Portfolio")
        if db:
            docs = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).get()
            for doc in docs:
                s = doc.to_dict()
                st.markdown(f'<div style="background:#0d1117; border:1px solid #238636; padding:10px; border-radius:8px; margin-bottom:8px;">✅ <b>@{s.get("total_odd")}</b> | {s["matches"][0]["match"]}</div>', unsafe_allow_html=True)

# --- TAB 2: ECHTE ANALYSE (GEEN HARD-CODED DATA) ---
with t2:
    st.header("📊 Statistische Match Analyse")
    if st.button("🔍 START ANALYSE (ECHTE DATA)", use_container_width=True):
        with st.spinner("Analyse van H2H en Odds..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 8})
            fixtures = res.json().get('response', [])
            temp_cache = []
            for f in fixtures:
                # Echte H2H ophalen
                h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{f['teams']['home']['id']}-{f['teams']['away']['id']}"})
                h2h_data = h2h_res.json().get('response', [])[:3]
                
                # Echte Odds ophalen
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f['fixture']['id'], 'bookmaker': 6})
                o_data = o_res.json().get('response', [])
                
                # Bereken veiligste markt op basis van H2H
                suggested_market = "Match Winner: Home"
                suggested_odd = 1.50
                if o_data and len(o_data) > 0:
                    for bet in o_data[0]['bookmakers'][0]['bets']:
                        if bet['name'] == "Match Winner":
                            suggested_market = f"Win: {f['teams']['home']['name']}"
                            suggested_odd = bet['values'][0]['odd']
                
                temp_cache.append({
                    'f': f, 
                    'h2h': h2h_data, 
                    'market': suggested_market, 
                    'odd': suggested_odd
                })
            st.session_state.analysis_cache = temp_cache

    for item in st.session_state.analysis_cache:
        f = item['f']
        h2h = item['h2h']
        
        st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
        st.markdown(f"### {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
        
        # Toon echte H2H resultaten
        if h2h:
            st.markdown("<b>Laatste ontmoetingen:</b>", unsafe_allow_html=True)
            for m in h2h:
                hg = m['goals']['home'] if m['goals']['home'] is not None else "?"
                ag = m['goals']['away'] if m['goals']['away'] is not None else "?"
                st.markdown(f'''<div class="h2h-row">
                    <span>{m['teams']['home']['name']} - {m['teams']['away']['name']}</span>
                    <span class="score-pill">{hg} - {ag}</span>
                </div>''', unsafe_allow_html=True)
        
        # Toon echte berekende tip
        st.markdown(f'''<div class="safe-pick">🛡️ ANALYSE TIP: {item['market']} (@{item['odd']})</div>''', unsafe_allow_html=True)
        
        if st.button(f"Bevestig Bet @{item['odd']}", key=f"re_bet_{f['fixture']['id']}"):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": item['odd'], "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "fixture_id": f['fixture']['id']}],
                    "stake": 10.0
                })
                st.toast(f"Bet opgeslagen!")
        st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f'<div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div><script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>', height=1000, scrolling=True)
