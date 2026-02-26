import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="ProPunter Master V22", page_icon="⚽", layout="wide")
TIMEZONE = "Europe/Brussels"
API_KEY = "0827af58298b4ce09f49d3b85e81818f"

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
    
    st.subheader("🎯 Strategie")
    min_prob = st.slider("Min. Slaagkans (%)", 5, 95, 10) # Lager gezet voor meer resultaat

    if st.button("🗑️ /Clear & Refund All"):
        refund = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund:.2f} hersteld!")
        time.sleep(0.5); st.rerun()

# --- MAIN ---
t1, t2, t3 = st.tabs(["⚡ Pro Generator", "📊 Portfolio", "📉 Live Scores"])

with t1:
    st.header("⚡ Live Scanner (Vandaag)")
    
    if st.button("🚀 FORCEER NIEUWE SCAN"):
        with st.spinner("Verse data ophalen..."):
            # We gebruiken 'upcoming' om de cache te omzeilen
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals,btts&oddsFormat=decimal"
            
            try:
                # We voegen een timestamp toe aan de request om caching te voorkomen
                r = requests.get(url, params={"_t": int(time.time())})
                
                if r.status_code == 200:
                    data = r.json()
                    targets = [1.5, 2.0, 3.0, 5.0]
                    found = {}
                    
                    for t in targets:
                        best_match = None
                        min_diff = 1.0
                        
                        for event in data:
                            for bm in event.get('bookmakers', []):
                                for market in bm.get('markets', []):
                                    m_key = market['key']
                                    for out in market['outcomes']:
                                        odds = out['price']
                                        prob = (1/odds)*100
                                        diff = abs(odds - t)
                                        
                                        if diff < min_diff and prob >= min_prob:
                                            min_diff = diff
                                            m_name = "WIN" if m_key == "h2h" else "O/U 2.5" if m_key == "totals" else "BTTS"
                                            best_match = {
                                                "match": f"{event['home_team']} vs {event['away_team']}",
                                                "odd": odds,
                                                "markt": f"{m_name}: {out['name']}",
                                                "tijd": datetime.fromisoformat(event['commence_time'].replace('Z', '')).strftime('%H:%M'),
                                                "prob": round(prob, 1)
                                            }
                        if best_match:
                            found[t] = best_match
                    
                    st.session_state.gen_slips = found
                    st.success(f"Laatste succesvolle scan: {datetime.now().strftime('%H:%M:%S')}")
                else:
                    st.error(f"Fout {r.status_code}: De API weigert de verbinding.")
            except Exception as e:
                st.error(f"Verbindingsfout: {e}")

    # DISPLAY KOLOMMEN
    if st.session_state.gen_slips:
        cols = st.columns(4)
        targets = [1.5, 2.0, 3.0, 5.0]
        for i, t in enumerate(targets):
            with cols[i]:
                if t in st.session_state.gen_slips:
                    info = st.session_state.gen_slips[t]
                    st.markdown(f"### Target {t}")
                    st.metric("Odd", f"@{info['odd']}")
                    st.write(f"**{info['match']}**")
                    st.info(info['markt'])
                    st.caption(f"🕒 {info['tijd']} | {info['prob']}%")
                    
                    stake = st.number_input(f"Inzet", min_value=1.0, value=10.0, key=f"s_{t}")
                    if st.button(f"Bevestig", key=f"b_{t}"):
                        if st.session_state.bankroll >= stake:
                            st.session_state.bankroll -= stake
                            st.session_state.active_bets.append({
                                "Match": info['match'], "Odd": info['odd'], "Inzet": stake, 
                                "Markt": info['markt'], "Tijd": info['tijd'], "Score": "0-0"
                            })
                            if user_id: auto_save(user_id)
                            st.rerun()

with t2:
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))

with t3:
    if st.session_state.active_bets:
        for b in st.session_state.active_bets:
            st.write(f"**{b['Match']}** - {b['Score']}")
            st.divider()
