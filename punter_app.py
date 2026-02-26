import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="ProPunter Master V24", page_icon="⚽", layout="wide")
TIMEZONE = "Europe/Brussels"

# JOUW API-FOOTBALL KEY (van dashboard.api-football.com)
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- DB INIT ---
HAS_DB = False
db = None
if "firebase" in st.secrets:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        HAS_DB = True
    except: pass

# --- HELPERS ---
def auto_save(u_id):
    if HAS_DB and u_id:
        try:
            db.collection("users").document(u_id).set({
                "bankroll": st.session_state.bankroll,
                "active_bets": st.session_state.active_bets,
                "last_update": datetime.now(pytz.timezone(TIMEZONE))
            })
        except: pass

def load_data(u_id):
    if HAS_DB and u_id:
        try:
            doc = db.collection("users").document(u_id).get()
            if doc.exists:
                d = doc.to_dict()
                return d.get("bankroll", 1000.0), d.get("active_bets", [])
        except: pass
    return 1000.0, []

# --- STATE ---
if 'bankroll' not in st.session_state: st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state: st.session_state.active_bets = []
if 'gen_slips' not in st.session_state: st.session_state.gen_slips = {}

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.caption("Provider: API-Football ✅")
    user_id = st.text_input("User ID", placeholder="bijv. pro_punter_01")
    
    col1, col2 = st.columns(2)
    if col1.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
    if col2.button("✨ Init Cloud"):
        if user_id: auto_save(user_id); st.success("Cloud OK")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")
    min_prob = st.slider("Min. Slaagkans (%)", 5, 95, 15)

    if st.button("🗑️ /Clear & Refund"):
        refund = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.rerun()

# --- MAIN ---
t1, t2, t3 = st.tabs(["⚡ Pro Generator", "📊 Portfolio", "📉 Live Scores"])

with t1:
    st.header("⚡ Live Scanner (API-Football)")
    
    if st.button("🚀 SCAN ALLE MARKTEN"):
        with st.spinner("Data ophalen via API-Football..."):
            headers = {
                'x-apisports-key': API_KEY,
                'x-rapidapi-host': 'v3.football.api-sports.io'
            }
            # We halen odds op voor de wedstrijden van vandaag
            params = {'date': datetime.now().strftime('%Y-%m-%d')}
            
            try:
                r = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
                data = r.json()
                
                if r.status_code == 200 and data.get('response'):
                    targets = [1.5, 2.0, 3.0, 5.0]
                    found = {}
                    
                    for target in targets:
                        best_match, min_diff = None, 1.0
                        for item in data['response']:
                            match_name = f"{item['fixture']['timezone']} - {item['league']['name']}"
                            # API-Football structureert odds per bookmaker
                            for bookmaker in item['bookmakers']:
                                # We paken de eerste grote bookmaker (bijv. 1xBet of Bet365)
                                for bet in bookmaker['bets']:
                                    if bet['name'] in ["Match Winner", "Goals Over/Under", "Both Teams Score"]:
                                        for value in bet['values']:
                                            odd = float(value['odd'])
                                            prob = (1/odd)*100
                                            diff = abs(odd - target)
                                            if diff < min_diff and prob >= min_prob:
                                                min_diff = diff
                                                best_match = {
                                                    "match": f"{item['fixture']['id']} - {item['league']['name']}",
                                                    "odd": odd,
                                                    "markt": f"{bet['name']}: {value['value']}",
                                                    "tijd": "Vandaag",
                                                    "prob": round(prob, 1)
                                                }
                        if best_match: found[target] = best_match
                    
                    st.session_state.gen_slips = found
                    st.success("Scan voltooid!")
                else:
                    st.error(f"Fout: {data.get('errors') or 'Geen data gevonden voor vandaag'}")
            except Exception as e:
                st.error(f"Connectiefout: {e}")

    # DISPLAY 4 KOLOMMEN
    if st.session_state.gen_slips:
        cols = st.columns(4)
        for i, t in enumerate([1.5, 2.0, 3.0, 5.0]):
            with cols[i]:
                if t in st.session_state.gen_slips:
                    info = st.session_state.gen_slips[t]
                    st.markdown(f"### Target {t}")
                    st.metric("Odd", f"@{info['odd']}")
                    st.info(info['markt'])
                    st.caption(f"{info['prob']}% kans")
                    stake = st.number_input(f"Inzet", min_value=1.0, value=10.0, key=f"s_{t}")
                    if st.button(f"Bevestig", key=f"b_{t}"):
                        if st.session_state.bankroll >= stake:
                            st.session_state.bankroll -= stake
                            st.session_state.active_bets.append({
                                "Match": info['match'], "Odd": info['odd'], "Inzet": stake, 
                                "Markt": info['markt'], "Score": "Live"
                            })
                            if user_id: auto_save(user_id)
                            st.rerun()

with t2:
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))

with t3:
    st.write("Live scores worden hier geladen zodra de wedstrijden starten.")
