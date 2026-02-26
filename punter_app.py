import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATIE ---
st.set_page_config(page_title="ProPunter Master V20.1", page_icon="⚽", layout="wide")
TIMEZONE = "Europe/Brussels"

# INGEBAKKEN API KEY (7500 requests/dag)
API_KEY = "0827af58298b4ce09f49d3b85e81818f"

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

# --- DATABASE HELPERS ---
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
    st.caption("Auto-Key: ✅ Geactiveerd (7500 req/dag)")
    
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    col_l, col_i = st.columns(2)
    if col_l.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
    if col_i.button("✨ Init Cloud"):
        if user_id: auto_save(user_id); st.success("Cloud Ready")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")
    
    st.subheader("🎯 Strategie")
    min_prob = st.slider("Min. Slaagkans (%)", 5, 95, 20)

    # DE CLEAR & REFUND FUNCTIE
    if st.button("🗑️ /Clear & Refund All"):
        refund = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund:.2f} hersteld!")
        time.sleep(1)
        st.rerun()

# --- MAIN INTERFACE ---
tab1, tab2, tab3 = st.tabs(["⚡ Pro Generator", "📊 Portefeuille", "📉 Live Center"])

with tab1:
    st.header("⚡ Live Scanner (Win, O/U, BTTS)")
    if st.button("🚀 SCAN ALLE MARKTEN"):
        with st.spinner("Data ophalen via API..."):
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals,btts&oddsFormat=decimal"
            try:
                r = requests.get(url)
                if r.status_code == 200:
                    data = r.json()
                    targets = [1.5, 2.0, 3.0, 5.0]
                    found = {}
                    for target in targets:
                        match_found = None
                        best_diff = 1.0 
                        for event in data:
                            for bm in event.get('bookmakers', []):
                                for market in bm.get('markets', []):
                                    m_type = market['key']
                                    for out in market['outcomes']:
                                        odds = out['price']
                                        prob = (1/odds)*100
                                        if abs(odds - target) < best_diff and prob >= min_prob:
                                            best_diff = abs(odds - target)
                                            m_name = "WIN" if m_type == "h2h" else "O/U 2.5" if m_type == "totals" else "BTTS"
                                            match_found = {
                                                "match": f"{event['home_team']} vs {event['away_team']}",
                                                "odd": odds, "markt": f"{m_name}: {out['name']}",
                                                "tijd": datetime.fromisoformat(event['commence_time'].replace('Z', '')).strftime('%H:%M'),
                                                "prob": round(prob, 1)
                                            }
                        if match_found: found[target] = match_found
                    st.session_state.generated_slips = found
                    st.success("Scanner Voltooid!")
                else: st.error(f"Fout: {r.status_code}")
            except: st.error("Netwerkfout.")

    if st.session_state.generated_slips:
        cols = st.columns(4)
        for i, (t, info) in enumerate(st.session_state.generated_slips.items()):
            with cols[i]:
                st.markdown(f"### Target {t}")
                st.metric("Odds", f"@{info['odd']}")
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

with tab2:
    if st.session_state.active_bets:
        st.dataframe(pd.DataFrame(st.session_state.active_bets), use_container_width=True)

with tab3:
    if st.session_state.active_bets:
        for b in st.session_state.active_bets:
            st.write(f"**{b['Match']}** | {b['Markt']} | Score: {b['Score']}")
            st.progress(0.1)
            st.divider()
