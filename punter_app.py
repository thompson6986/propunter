import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V93", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 5px solid #1f6feb; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 10px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; }
    .tracker-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
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

# --- TAB 2: ANALYSE (MET ECHTE ODDS) ---
with t2:
    st.header("📊 Deep Match Analysis")
    if st.button("🔍 SCAN EUROPESE AVOND (LIVE ODDS)", use_container_width=True):
        with st.spinner("Real-time data ophalen..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
            data = res.json().get('response', [])
            # Filter op Europa League (3) en Conference (848)
            euro_fix = [f for f in data if f['league']['id'] in [3, 848]]
            
            results = []
            for f in euro_fix[:10]:
                f_id = f['fixture']['id']
                # Haal de echte odds van Bet365 (ID: 8) of Bwin (ID: 6)
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': 8})
                o_data = o_res.json().get('response', [])
                
                final_odd = 1.0
                final_market = "Match Winner"
                
                if o_data:
                    for bet in o_data[0]['bookmakers'][0]['bets']:
                        if bet['name'] == "Match Winner":
                            final_market = f"Win: {f['teams']['home']['name']}"
                            final_odd = float(bet['values'][0]['odd'])
                
                results.append({
                    'id': f_id, 'home': f['teams']['home']['name'], 'away': f['teams']['away']['name'],
                    'start': datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M'),
                    'market': final_market, 'odd': final_odd, 'league': f['league']['name']
                })
            st.session_state.analysis_results = results

    for item in st.session_state.analysis_results:
        st.markdown(f'''
            <div class="analysis-card">
                <div style="display:flex; justify-content:space-between;">
                    <b>{item['home']} vs {item['away']}</b>
                    <span>🕒 {item['start']}</span>
                </div>
                <div class="safe-pick" style="margin-top:10px;">🛡️ TIP: {item['market']} (@{item['odd']})</div>
            </div>
        ''', unsafe_allow_html=True)
        if st.button(f"➕ Toevoegen", key=f"add_{item['id']}"):
            st.session_state.my_selections.append(item)
            st.toast(f"{item['home']} toegevoegd!")

# --- TAB 1: BUILDER ---
with t1:
    st.header("📝 Betslip Builder")
    if not st.session_state.my_selections:
        st.info("Voeg wedstrijden toe via de 'Deep Analysis' tab.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.write(f"✅ **{sel['home']} vs {sel['away']}** | {sel['market']} (@{sel['odd']})")
        
        st.divider()
        st.subheader(f"Totaal Odd: @{total_odd:.2f}")
        if st.button("🔥 BEVESTIG EN OPSLAAN IN TRACKER", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2), "matches": st.session_state.my_selections,
                    "stake": 10.0, "status": "OPEN"
                })
                st.session_state.my_selections = []
                st.success("Slip succesvol naar de tracker gestuurd!"); st.rerun()

# --- TAB 3: TRACKER (HERSTELD) ---
with t3:
    st.header("📈 Bankroll & Tracker")
    if db:
        slips = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).get()
        for slip in slips:
            s = slip.to_dict()
            st.markdown(f'''
                <div class="tracker-card">
                    <div style="display:flex; justify-content:space-between;">
                        <b>Combinatie @{s['total_odd']}</b>
                        <span>🕒 {s['timestamp'].strftime('%d/%m %H:%M')}</span>
                    </div>
                    <hr style="border:0.5px solid #30363d; margin:10px 0;">
                    {s['matches'][0]['match']} | {s['matches'][0].get('market')}
                    <div style="margin-top:10px;">Potentiële Winst: <span class="potential-win">€{s['total_odd'] * 10:.2f}</span></div>
                </div>
            ''', unsafe_allow_html=True)
