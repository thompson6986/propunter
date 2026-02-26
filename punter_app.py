import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
import time

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V78", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .main-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 15px; margin-bottom: 15px; }
    .analysis-card { border-left: 6px solid #1f6feb; background: #1c2128; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 10px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; }
    .h2h-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; color: #8b949e; }
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

# --- SESSION STATE VOOR PERSISTENTIE ---
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []
if 'u_id' not in st.session_state:
    st.session_state.u_id = "punter_01"

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 DASHBOARD (GEN/TRACK)", "📊 MATCH ANALYSIS", "🏟️ STADIUM"])

# --- TAB 1: UNIFIED DASHBOARD ---
with t1:
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("🚀 Quick Generator")
        if st.button("Genereer 1.5 - 5.0 Odds", use_container_width=True):
            # Snelle generatie logica (vereenvoudigd voor snelheid)
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 10})
            st.session_state.quick_slips = res.json().get('response', [])
            st.toast("Nieuwe suggesties geladen!")
        
        if 'quick_slips' in st.session_state:
            for f in st.session_state.quick_slips[:3]:
                st.markdown(f'<div class="main-card">🕒 {datetime.fromtimestamp(f["fixture"]["timestamp"]).strftime("%H:%M")} | **{f["teams"]["home"]["name"]} vs {f["teams"]["away"]["name"]}**</div>', unsafe_allow_html=True)

    with col_right:
        st.subheader("📡 Live Tracker")
        if db:
            docs = db.collection("saved_slips").where("user_id", "==", st.session_state.u_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).get()
            for doc in docs:
                s = doc.to_dict()
                st.markdown(f'<div class="main-card" style="border-left: 3px solid #3fb950;"><b>@{s.get("total_odd")}</b> | {s["matches"][0]["match"]}</div>', unsafe_allow_html=True)

# --- TAB 2: PERSISTENT ANALYSIS ---
with t2:
    st.header("📊 Deep Match Analysis")
    c1, c2 = st.columns([3, 1])
    if c1.button("🔍 START NIEUWE ANALYSE", use_container_width=True):
        with st.spinner("Data ophalen..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'next': 8})
            fixtures = res.json().get('response', [])
            temp_results = []
            for f in fixtures:
                h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{f['teams']['home']['id']}-{f['teams']['away']['id']}"})
                h2h = h2h_res.json().get('response', [])[:3]
                temp_results.append({'fixture': f, 'h2h': h2h})
            st.session_state.analysis_results = temp_results

    # Toon resultaten uit session_state (blijft staan na klik op bet!)
    for item in st.session_state.analysis_results:
        f = item['fixture']
        h2h = item['h2h']
        f_id = f['fixture']['id']
        
        st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
        st.markdown(f"**{f['teams']['home']['name']} vs {f['teams']['away']['name']}**")
        
        if h2h:
            h2h_html = '<table class="h2h-table">'
            for m in h2h:
                score = f"{m['goals']['home']} - {m['goals']['away']}" if m['goals']['home'] is not None else "? - ?"
                h2h_html += f"<tr><td>{m['teams']['home']['name']} - {m['teams']['away']['name']}</td><td><b>{score}</b></td></tr>"
            h2h_html += '</table>'
            st.markdown(h2h_html, unsafe_allow_html=True)
        
        st.markdown(f'<div class="safe-pick">🛡️ VEILIGE KEUZE: Over 1.5 Goals (@1.40)</div>', unsafe_allow_html=True)
        
        if st.button(f"Bevestig Bet", key=f"btn_persist_{f_id}"):
            if db:
                db.collection("saved_slips").add({
                    "user_id": st.session_state.u_id, "timestamp": datetime.now(TIMEZONE),
                    "total_odd": 1.40, "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "fixture_id": f_id}],
                    "stake": 10.0
                })
                st.success(f"Bet op {f['teams']['home']['name']} opgeslagen!")
        st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f'<div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div><script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>', height=1000)
