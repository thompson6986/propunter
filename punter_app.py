import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V96", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 5px solid #f1e05a; }
    .market-tag { background: #23863622; color: #3fb950; padding: 8px 12px; border-radius: 6px; font-weight: bold; border: 1px solid #238636; }
    .odd-value { color: #58a6ff; font-size: 1.2rem; font-weight: bold; font-family: monospace; }
    .tracker-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE STATE ---
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

# --- TAB 2: ANALYSE (TRUE DATA LOGIC) ---
with t2:
    st.header("📊 Deep Match Analysis")
    if st.button("🔍 SCAN LIVE EUROPESE ODDS", use_container_width=True):
        with st.spinner("Real-time marktdata ophalen uit API..."):
            try:
                # We pakken de eerstvolgende 15 Europese matchen (EL/ECL)
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26', 'league': '3'}) # EL
                res_ecl = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26', 'league': '848'}) # ECL
                
                data = res.json().get('response', []) + res_ecl.json().get('response', [])
                
                temp_results = []
                for f in data[:12]:
                    f_id = f['fixture']['id']
                    
                    # SCAN ALLE BOOKMAKERS VOOR ECHTE ODDS
                    o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                    o_data = o_res.json().get('response', [])
                    
                    real_odd = None
                    real_market = None
                    
                    if o_data:
                        # We pakken de eerste beschikbare bookmaker die 'Match Winner' heeft
                        for bm in o_data[0]['bookmakers']:
                            for bet in bm['bets']:
                                if bet['name'] in ["Match Winner", "Home/Away"]:
                                    real_market = f"Win: {f['teams']['home']['name']}"
                                    real_odd = float(bet['values'][0]['odd'])
                                    break
                            if real_odd: break

                    # Alleen toevoegen als we ECHTE data hebben gevonden
                    if real_odd and real_odd != 1.45:
                        temp_results.append({
                            'id': str(f_id), 
                            'home': f['teams']['home']['name'], 
                            'away': f['teams']['away']['name'],
                            'start': datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M'),
                            'market': real_market, 
                            'odd': real_odd,
                            'league': f['league']['name']
                        })
                st.session_state.analysis_results = temp_results
            except Exception as e:
                st.error(f"Fout bij scannen: {e}")

    # RENDER ANALYSE (ZONDER PLACEHOLDERS)
    if not st.session_state.analysis_results:
        st.info("Klik op de scan-knop om de actuele Europese markt te laden.")
    
    for item in st.session_state.analysis_results:
        st.markdown(f'''
            <div class="analysis-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <small style="color:#8b949e;">{item['league']} | 🕒 {item['start']}</small><br>
                        <b style="font-size:1.2rem;">{item['home']} vs {item['away']}</b>
                    </div>
                    <div class="odd-value">@{item['odd']}</div>
                </div>
                <div style="margin-top:15px; display:flex; justify-content:space-between; align-items:center;">
                    <div class="market-tag">🛡️ TIP: {item['market']}</div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        if st.button(f"➕ Voeg {item['home']} toe aan mijn slip", key=f"v96_{item['id']}"):
            if item not in st.session_state.my_selections:
                st.session_state.my_selections.append(item)
                st.toast(f"{item['home']} toegevoegd!")

# --- TAB 1: BUILDER (COMBINATIE LOGICA) ---
with t1:
    st.header("📝 Betslip Builder")
    if not st.session_state.my_selections:
        st.info("Geen selecties. Gebruik de 'Deep Analysis' tab.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.markdown(f"✅ **{sel['home']} vs {sel['away']}** (@{sel['odd']})")
        
        st.divider()
        st.subheader(f"Gecombineerde Odd: @{total_odd:.2f}")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Wis Slip", use_container_width=True):
            st.session_state.my_selections = []; st.rerun()
        if c2.button("🔥 BEVESTIG EN OPSLAAN", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2), "matches": st.session_state.my_selections,
                    "stake": 10.0, "status": "OPEN"
                })
                st.session_state.my_selections = []
                st.success("Opgeslagen in de tracker!"); st.rerun()

# --- TAB 3: TRACKER ---
with t3:
    st.header("📈 Jouw Betting Historie")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        for doc in docs:
            s = doc.to_dict()
            st.markdown(f'''
                <div class="tracker-card">
                    <b>Slip @{s['total_odd']}</b> | 🕒 {s['timestamp'].strftime('%H:%M')}<br>
                    <small style="color:#8b949e;">Matches: {len(s['matches'])} | Inzet: €10</small>
                </div>
            ''', unsafe_allow_html=True)
            
