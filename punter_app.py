import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Europe", page_icon="🇪🇺", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- EUROPESE LEAGUE IDS (EL & ECL) ---
EUROPEAN_LEAGUES = [3, 4, 5, 2, 848] # Europa League, Conference League, Champions League, etc.

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #f1e05a; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 12px; border-radius: 8px; border: 1px dotted #238636; font-weight: bold; margin-top: 15px; }
    .h2h-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #21262d; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
@st.cache_resource
def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- APP TABS ---
t1, t2, t3 = st.tabs(["🚀 DASHBOARD", "📊 EUROPEAN ANALYSIS", "🏟️ STADIUM"])

with t2:
    st.header("🇪🇺 European Night Analyzer")
    st.info("Focus: Europa League & Conference League wedstrijden van vanavond.")
    
    if st.button("🔍 SCAN EUROPESE AVOND", use_container_width=True):
        with st.spinner("Topmatchen aan het analyseren..."):
            # We scannen de fixtures en filteren op Europese League IDs
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
            all_fixtures = res.json().get('response', [])
            
            # Filter enkel op Europese topcompetities
            euro_fixtures = [f for f in all_fixtures if f['league']['id'] in EUROPEAN_LEAGUES]
            
            st.session_state.euro_cache = []
            for f in euro_fixtures[:10]: # De belangrijkste 10 matchen
                f_id = f['fixture']['id']
                
                # Haal de echte Odds op
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 6})
                o_data = o_res.json().get('response', [])
                
                # Haal H2H historie op
                h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{f['teams']['home']['id']}-{f['teams']['away']['id']}"})
                h2h_list = h2h_res.json().get('response', [])[:3]
                
                # Bepaal markt & odd
                market_name = "Match Winner"
                market_odd = 1.0
                if o_data:
                    for bet in o_data[0]['bookmakers'][0]['bets']:
                        if bet['name'] == "Match Winner":
                            market_name = f"Win: {f['teams']['home']['name']}"
                            market_odd = bet['values'][0]['odd']
                        elif bet['name'] == "Goals Over/Under" and market_odd == 1.0:
                            market_name = "Over 1.5 Goals"
                            market_odd = bet['values'][0]['odd']

                st.session_state.euro_cache.append({
                    'f': f, 'h2h': h2h_list, 'market': market_name, 'odd': market_odd
                })

    # Render Analyse
    if 'euro_cache' in st.session_state:
        for item in st.session_state.euro_cache:
            f = item['f']
            st.markdown(f'<div class="analysis-card">', unsafe_allow_html=True)
            st.markdown(f"### 🏟️ {f['league']['name']}: {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            st.caption(f"🕒 Aftrap: {datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')}")
            
            if item['h2h']:
                st.markdown("**Historiek:**")
                for h in item['h2h']:
                    hg = h['goals']['home'] if h['goals']['home'] is not None else "-"
                    ag = h['goals']['away'] if h['goals']['away'] is not None else "-"
                    st.markdown(f'''<div class="h2h-row">
                        <span>{h['teams']['home']['name']} - {h['teams']['away']['name']}</span>
                        <span style="font-weight:bold;">{hg} - {ag}</span>
                    </div>''', unsafe_allow_html=True)

            st.markdown(f'''<div class="safe-pick">🛡️ VEILIGE KEUZE: {item['market']} (@{item['odd']})</div>''', unsafe_allow_html=True)
            
            if st.button(f"Plaats op {f['teams']['home']['name']}", key=f"euro_btn_{f['fixture']['id']}"):
                if db:
                    db.collection("saved_slips").add({
                        "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                        "total_odd": item['odd'], "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": item['market'], "odd": item['odd']}],
                        "stake": 10.0
                    })
                    st.toast("Bet verwerkt!")
            st.markdown('</div>', unsafe_allow_html=True)
