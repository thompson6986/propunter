import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATIE ---
st.set_page_config(page_title="ProPunter Master V19.2", page_icon="⚽", layout="wide")
TIMEZONE = "Europe/Brussels"

# --- DATABASE INITIALISATIE ---
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
def auto_save(user_id):
    if HAS_DB and user_id:
        try:
            db.collection("users").document(user_id).set({
                "bankroll": st.session_state.bankroll,
                "active_bets": st.session_state.active_bets,
                "last_update": datetime.now(pytz.timezone(TIMEZONE))
            })
        except: pass

def load_data(user_id):
    if HAS_DB and user_id:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                d = doc.to_dict()
                return d.get("bankroll", 1000.0), d.get("active_bets", [])
        except: pass
    return 1000.0, []

# --- SESSION STATE ---
if 'bankroll' not in st.session_state: st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state: st.session_state.active_bets = []
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.subheader("🔑 API Instellingen")
    
    # Gebruik hier je eigen key met 7500 requests
    api_key_input = st.text_input("Odds API Key", value="0827af58298b4ce09f49d3b85e81818f", type="password")
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    c1, c2 = st.columns(2)
    if c1.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
    if c2.button("✨ Init Cloud"):
        if user_id: auto_save(user_id); st.success("Verbonden!")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")
    min_prob = st.slider("Min. Slaagkans (%)", 10, 95, 20)

    # DE VERBETERDE CLEAR FUNCTIE (REFUND)
    if st.button("🗑️ /Clear & Refund All"):
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund_total:.2f} hersteld.")
        time.sleep(1); st.rerun()

# --- TABS ---
t1, t2, t3 = st.tabs(["⚡ Pro Generator", "📊 Portefeuille", "📉 Live Scores"])

with t1:
    st.header("⚡ Berekende Slips (Win, O/U, BTTS)")
    if st.button("🚀 SCAN ALLE MARKTEN"):
        with st.spinner("Laden van 7500+ data punten..."):
            # We halen alle voetbalwedstrijden op
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key_input}&regions=eu&markets=h2h,totals,btts&oddsFormat=decimal"
            try:
                r = requests.get(url)
                if r.status_code == 200:
                    data = r.json()
                    targets = [1.5, 2.0, 3.0, 5.0]
                    found = {}
                    for target in targets:
                        best_match = None
                        min_diff = 0.8
                        for event in data:
                            for bm in event.get('bookmakers', []):
                                for market in bm.get('markets', []):
                                    m_type = market['key']
                                    for out in market['outcomes']:
                                        odds = out['price']
                                        prob = (1/odds)*100
                                        if abs(odds - target) < min_diff and prob >= min_prob:
                                            min_diff = abs(odds - target)
                                            m_name = "WIN" if m_type == "h2h" else "O/U 2.5" if m_type == "totals" else "BTTS"
                                            best_match = {
                                                "match": f"{event['home_team']} vs {event['away_team']}",
                                                "odd": odds, "markt": f"{m_name}: {out['name']}",
                                                "tijd": datetime.fromisoformat(event['commence_time'].replace('Z', '')).strftime('%H:%M'),
                                                "prob": round(prob, 1)
                                            }
                        if best_match: found[target] = best_match
                    st.session_state.generated_slips = found
                    st.success("Scanner Voltooid!")
                else:
                    st.error(f"API Fout {r.status_code}. Controleer of je key geactiveerd is.")
            except: st.error("Kan geen verbinding maken met de server.")

    if st.session_state.generated_slips:
        cols = st.columns(4)
        for i, (t, info) in enumerate(st.session_state.generated_slips.items()):
            with cols[i]:
                st.subheader(f"Target {t}")
                st.metric("Odds", f"@{info['odd']}")
                st.write(f"**{info['match']}**")
                st.info(info['markt'])
                st.caption(f"🕒 {info['tijd']} | {info['prob']}% kans")
                stake = st.number_input("Inzet", min_value=1.0, value=10.0, key=f"s_{t}")
                if st.button(f"Zet In @{info['odd']}", key=f"b_{t}"):
                    if st.session_state.bankroll >= stake:
                        st.session_state.bankroll -= stake
                        st.session_state.active_bets.append({
                            "Match": info['match'], "Odd": info['odd'], "Inzet": stake, 
                            "Markt": info['markt'], "Tijd": info['tijd'], "Score": "Live"
                        })
                        if user_id: auto_save(user_id)
                        st.rerun()

with t2:
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))
    else: st.info("Geen openstaande weddenschappen.")

with t3:
    st.header("📉 Real-time Score Monitoring")
    if st.session_state.active_bets:
        for b in st.session_state.active_bets:
            with st.expander(f"⚽ {b['Match']} ({b['Tijd']})", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Markt:** {b['Markt']}")
                c2.write(f"**Odd:** @{b['Odd']}")
                c3.write(f"**Score:** 0-0") # Hier kan later de live-score API aan
                st.progress(0.0)
    else: st.warning("Plaats eerst een bet om scores te volgen.")
