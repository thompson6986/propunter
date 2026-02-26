import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V97", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 5px solid #1f6feb; }
    .odd-box { background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; text-align: center; min-width: 80px; }
    .market-label { color: #3fb950; font-weight: bold; border: 1px solid #238636; padding: 4px 8px; border-radius: 5px; background: #23863611; }
    </style>
    """, unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
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

# --- TAB 2: ANALYSE (CRASH-PROOF) ---
with t2:
    st.header("📊 Deep Match Analysis")
    if st.button("🔍 SCAN LIVE EUROPESE MARKTEN", use_container_width=True):
        with st.spinner("Real-time data ophalen..."):
            try:
                # Scannen van EL (3) en ECL (848)
                res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
                data = res.json().get('response', [])
                
                temp_results = []
                for f in data:
                    league_id = f.get('league', {}).get('id')
                    if league_id in [3, 848]:
                        f_id = f.get('fixture', {}).get('id')
                        
                        # ECHTE ODDS SCAN (Multiple Bookmakers fallback)
                        o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                        o_data = o_res.json().get('response', [])
                        
                        best_odd = 0.0
                        best_market = "Wachten op markt..."
                        
                        if o_data:
                            for bm in o_data[0].get('bookmakers', []):
                                for bet in bm.get('bets', []):
                                    if bet.get('name') == "Match Winner":
                                        best_market = f"Win: {f['teams']['home']['name']}"
                                        best_odd = float(bet['values'][0]['odd'])
                                        break
                                if best_odd > 0: break

                        if best_odd > 1.0: # Enkel matchen met echte odds tonen
                            temp_results.append({
                                'id': str(f_id),
                                'home': f['teams']['home']['name'],
                                'away': f['teams']['away']['name'],
                                'league': f['league']['name'],
                                'start': datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M'),
                                'market': best_market,
                                'odd': best_odd
                            })
                st.session_state.analysis_results = temp_results
            except Exception as e:
                st.error(f"Data error: {e}")

    # RENDERING MET .GET() VEILIGHEID
    for item in st.session_state.analysis_results:
        f_id = item.get('id', '0')
        st.markdown(f'''
            <div class="analysis-card">
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <div>
                        <small style="color:#8b949e;">{item.get('league', 'Europa')} | 🕒 {item.get('start', 'Vandaag')}</small><br>
                        <b style="font-size:1.1rem;">{item.get('home', 'Team A')} vs {item.get('away', 'Team B')}</b>
                    </div>
                    <div class="odd-box"><b style="color:#58a6ff;">@{item.get('odd', 1.0)}</b></div>
                </div>
                <div style="margin-top:15px; display:flex; justify-content:space-between; align-items:center;">
                    <span class="market-label">🛡️ {item.get('market', 'Match Winner')}</span>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        if st.button(f"➕ Voeg {item.get('home')} toe aan slip", key=f"v97_{f_id}"):
            st.session_state.my_selections.append(item)
            st.toast(f"Toegevoegd: {item.get('home')}")

# --- TAB 1: BUILDER ---
with t1:
    st.header("📝 Jouw Custom Betslip")
    if not st.session_state.my_selections:
        st.info("Kies wedstrijden in de analyse-tab om je slip te bouwen.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel.get('odd', 1.0)
            st.write(f"✅ **{sel.get('home')} vs {sel.get('away')}** (@{sel.get('odd')})")
        
        st.divider()
        st.subheader(f"Gecumuleerde Odd: @{total_odd:.2f}")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Wis Alles", use_container_width=True):
            st.session_state.my_selections = []; st.rerun()
        if c2.button("🔥 BEVESTIG EN OPSLAAN", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2), "matches": st.session_state.my_selections,
                    "stake": 10.0, "status": "OPEN"
                })
                st.session_state.my_selections = []
                st.success("Succesvol naar Tracker gestuurd!"); st.rerun()

# --- TAB 3: TRACKER ---
with t3:
    st.header("📈 Bankroll Management")
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).get()
        for doc in docs:
            s = doc.to_dict()
            st.markdown(f'''
                <div style="background:#0d1117; border:1px solid #30363d; border-radius:10px; padding:15px; margin-bottom:10px;">
                    <b>Slip @{s.get('total_odd')}</b> | {s['timestamp'].strftime('%d/%m %H:%M')}<br>
                    <span style="color:#3fb950; font-weight:bold;">Winst: €{s.get('total_odd', 0) * 10:.2f}</span>
                </div>
            ''', unsafe_allow_html=True)
