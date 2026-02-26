import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATIE ---
st.set_page_config(page_title="ProPunter Master V18.4", page_icon="⚽", layout="wide")
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
    except Exception as e:
        st.sidebar.error(f"🔌 Database verbinding mislukt: {e}")

# --- HELPERS ---
def auto_save(user_id):
    if HAS_DB and user_id:
        try:
            db.collection("users").document(user_id).set({
                "bankroll": st.session_state.bankroll,
                "active_bets": st.session_state.active_bets,
                "last_update": datetime.now(pytz.timezone(TIMEZONE))
            })
        except Exception as e:
            st.error(f"Fout bij opslaan: {e}")

def load_data(user_id):
    if HAS_DB and user_id:
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("bankroll", 1000.0), data.get("active_bets", [])
        except Exception as e:
            st.error(f"Fout bij laden: {e}")
    return 1000.0, []

# --- SESSION STATE ---
if 'bankroll' not in st.session_state: st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state: st.session_state.active_bets = []
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.subheader("🔑 API & User")
    api_key_input = st.text_input("The Odds API Key", value="0827af58298b4ce09f49d3b85e81818f", type="password")
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    col_l, col_i = st.columns(2)
    if col_l.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
    if col_i.button("✨ Init"):
        if user_id: auto_save(user_id); st.success("Cloud Gesynchroniseerd!")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")
    min_prob = st.slider("Min. Slaagkans (%)", 10, 95, 25)

    if st.button("🗑️ /Clear & Refund All"):
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund_total:.2f} hersteld.")
        time.sleep(1); st.rerun()

# --- MAIN INTERFACE ---
tab1, tab2, tab3 = st.tabs(["⚡ Pro Generator", "📊 Portefeuille", "📉 Live Center"])

with tab1:
    st.header("⚡ Professionele Markt Scanner")
    if st.button("🚀 GENEREER SLIPS"):
        with st.spinner("Live odds scannen..."):
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key_input}&regions=eu&markets=h2h,totals,btts&oddsFormat=decimal"
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    data = res.json()
                    targets = [1.5, 2.0, 3.0, 5.0]
                    found = {}
                    for t in targets:
                        best_match = None
                        min_diff = 999
                        for event in data:
                            for bm in event.get('bookmakers', []):
                                for market in bm.get('markets', []):
                                    m_type = market['key']
                                    for outcome in market.get('outcomes', []):
                                        odds = outcome['price']
                                        prob = (1/odds)*100
                                        diff = abs(odds - t)
                                        if diff < min_diff and diff < 0.8 and prob >= min_prob:
                                            min_diff = diff
                                            display_m = "WIN" if m_type == "h2h" else "O/U 2.5" if m_type == "totals" else "BTTS"
                                            best_match = {
                                                "match": f"{event['home_team']} vs {event['away_team']}",
                                                "odd": odds,
                                                "markt": f"{display_m}: {outcome['name']}",
                                                "tijd": datetime.fromisoformat(event['commence_time'].replace('Z', '')).strftime('%H:%M'),
                                                "prob": round(prob, 1)
                                            }
                        if best_match: found[t] = best_match
                    st.session_state.generated_slips = found
                else: st.error(f"API Error {res.status_code}")
            except Exception as e: st.error(f"Fout: {e}")

    if st.session_state.generated_slips:
        cols = st.columns(4)
        for i, (t, info) in enumerate(st.session_state.generated_slips.items()):
            with cols[i]:
                st.markdown(f"### Target {t}")
                st.metric("Odd", f"@{info['odd']}")
                st.write(f"**{info['match']}**")
                st.info(f"{info['markt']}")
                st.caption(f"🕒 {info['tijd']} | Kans: {info['prob']}%")
                stake = st.number_input(f"Inzet", min_value=1.0, value=10.0, key=f"s_{t}")
                if st.button(f"Plaats @{info['odd']}", key=f"b_{t}"):
                    if st.session_state.bankroll >= stake:
                        st.session_state.bankroll -= stake
                        st.session_state.active_bets.append({
                            "Match": info['match'], "Odd": info['odd'], "Inzet": stake, 
                            "Markt": info['markt'], "Tijd": info['tijd'], "Score": "0-0"
                        })
                        if user_id: auto_save(user_id)
                        st.rerun()

with tab2:
    st.header("📊 Actieve Weddenschappen")
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))
    else: st.info("Geen openstaande bets.")

with tab3:
    st.header("📉 Live Center")
    if st.session_state.active_bets:
        for bet in st.session_state.active_bets:
            st.write(f"**{bet['Match']}** - {bet['Markt']} | Score: {bet['Score']}")
            st.progress(0.1)
