import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V94", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 6px solid #1f6feb; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 10px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; }
    .tracker-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 12px; border-top: 3px solid #3fb950; }
    .potential-win { color: #3fb950; font-size: 1.1rem; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DB & SESSION STATE ---
if 'my_selections' not in st.session_state: st.session_state.my_selections = []
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []

@st.cache_resource
def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- TABS ---
t1, t2, t3 = st.tabs(["🚀 BETSLIP BUILDER", "📊 DEEP ANALYSIS", "📈 TRACKER"])

# --- TAB 2: ANALYSE (MET DATA-STABILITEIT) ---
with t2:
    st.header("📊 Deep Match Analysis")
    if st.button("🔍 SCAN EUROPESE AVOND", use_container_width=True):
        with st.spinner("Real-time data ophalen..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
            data = res.json().get('response', [])
            euro_fix = [f for f in data if f.get('league') and f['league']['id'] in [3, 848]]
            
            temp_results = []
            for f in euro_fix[:10]:
                f_id = f['fixture']['id']
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 8})
                o_data = o_res.json().get('response', [])
                
                # Echte odds ophalen of fallback
                final_odd = 1.45
                final_market = "Win or Draw (1X)"
                if o_data and len(o_data) > 0:
                    for bet in o_data[0]['bookmakers'][0]['bets']:
                        if bet['name'] == "Match Winner":
                            final_market = f"Win: {f['teams']['home']['name']}"
                            final_odd = float(bet['values'][0]['odd'])
                
                temp_results.append({
                    'id': str(f_id), 
                    'home': f['teams']['home']['name'], 
                    'away': f['teams']['away']['name'],
                    'start': datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M'),
                    'market': final_market, 
                    'odd': final_odd
                })
            st.session_state.analysis_results = temp_results

    # Veilig renderen van resultaten
    for item in st.session_state.analysis_results:
        st.markdown(f'''
            <div class="analysis-card">
                <div style="display:flex; justify-content:space-between;">
                    <b>{item.get('home', 'Team')} vs {item.get('away', 'Team')}</b>
                    <span>🕒 {item.get('start', '--:--')}</span>
                </div>
                <div class="safe-pick" style="margin-top:10px;">🛡️ TIP: {item.get('market')} (@{item.get('odd')})</div>
            </div>
        ''', unsafe_allow_html=True)
        if st.button(f"➕ Voeg toe", key=f"add_v94_{item['id']}"):
            st.session_state.my_selections.append(item)
            st.toast(f"{item['home']} toegevoegd aan builder!")

# --- TAB 1: BUILDER ---
with t1:
    st.header("📝 Jouw Betslip")
    if not st.session_state.my_selections:
        st.info("Selecteer eerst wedstrijden in de 'Deep Analysis' tab.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.write(f"✅ **{sel['home']} vs {sel['away']}** | @{sel['odd']}")
        
        st.divider()
        st.subheader(f"Totaal Odd: @{total_odd:.2f}")
        if st.button("🔥 BEVESTIG EN PLAATS BET", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", 
                    "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2), 
                    "matches": st.session_state.my_selections,
                    "stake": 10.0
                })
                st.session_state.my_selections = []
                st.success("Succes! Je bet staat nu in de Tracker."); st.rerun()

# --- TAB 3: TRACKER (ROBUUST) ---
with t3:
    st.header("📈 Bankroll Tracker")
    if db:
        slips = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        for slip in slips:
            s = slip.to_dict()
            first_match = s['matches'][0] if s.get('matches') else {"match": "Onbekend"}
            st.markdown(f'''
                <div class="tracker-card">
                    <div style="display:flex; justify-content:space-between;">
                        <b>Combinatie @{s.get('total_odd', 0)}</b>
                        <span style="color:#8b949e; font-size:0.8rem;">{s['timestamp'].strftime('%H:%M')}</span>
                    </div>
                    <div style="margin:10px 0;">{first_match.get('home', 'Team')} vs {first_match.get('away', 'Team')}</div>
                    <div class="potential-win">Winst: €{s.get('total_odd', 0) * 10:.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
