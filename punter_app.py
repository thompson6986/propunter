import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATIE ---
st.set_page_config(page_title="ProPunter Master V18", page_icon="⚽", layout="wide")
TIMEZONE = "Europe/Brussels"
API_KEY_ODDS = "0827af58298b4ce09f49d3b85e81818f" 

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
        st.sidebar.error(f"⚠️ Databasefout: {e}")

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
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get("bankroll", 1000.0), data.get("active_bets", [])
    return 1000.0, []

# --- SESSION STATE ---
if 'bankroll' not in st.session_state: st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state: st.session_state.active_bets = []
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    c_l, c_i = st.columns(2)
    if c_l.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
    if c_i.button("✨ Init"):
        if user_id: auto_save(user_id); st.success("Gesynct!")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")

    # --- CUSTOM FILTERS ---
    st.subheader("🎯 Strategie Instellingen")
    target_odd = st.slider("Doel Odd", 1.10, 10.0, 2.0, 0.1)
    min_prob = st.slider("Minimaal Slaagpercentage (%)", 10, 95, 50)
    
    st.divider()
    if st.button("🗑️ /Clear & Refund All"):
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success("Bankroll hersteld.")
        time.sleep(1); st.rerun()

# --- MAIN INTERFACE ---
tab1, tab2, tab3 = st.tabs(["⚡ Custom Generator", "📊 Dashboard", "📉 Live Center"])

with tab1:
    st.header("⚡ Custom Strategy Scanner")
    st.write(f"Zoeken naar odds rond de **{target_odd}** met een impliciete slaagkans van minstens **{min_prob}%**.")
    
    if st.button("🚀 SCAN DE MARKT"):
        with st.spinner("Markten analyseren..."):
            markets = "h2h,totals,btts"
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY_ODDS}&regions=eu&markets={markets}&oddsFormat=decimal"
            
            try:
                res = requests.get(url)
                data = res.json()
                found = []

                for event in data:
                    for bm in event.get('bookmakers', []):
                        for market in bm.get('markets', []):
                            m_key = market['key']
                            for outcome in market.get('outcomes', []):
                                odds = outcome['price']
                                # Bereken impliciete kans (1/odds)
                                implicit_prob = (1 / odds) * 100
                                
                                # Filter op basis van jouw input
                                if abs(odds - target_odd) < 0.5 and implicit_prob >= min_prob:
                                    found.append({
                                        "match": f"{event['home_team']} vs {event['away_team']}",
                                        "odd": odds,
                                        "prob": round(implicit_prob, 1),
                                        "markt": f"{m_key}: {outcome['name']}",
                                        "tijd": datetime.fromisoformat(event['commence_time'].replace('Z', '')).strftime('%H:%M')
                                    })
                
                # Sorteer op beste match met target_odd
                st.session_state.generated_slips = sorted(found, key=lambda x: abs(x['odd'] - target_odd))[:8]
                st.success(f"{len(st.session_state.generated_slips)} matches gevonden.")
            except:
                st.error("API error.")

    if st.session_state.generated_slips:
        for i, info in enumerate(st.session_state.generated_slips):
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.write(f"**{info['match']}**")
                c2.write(f"Odd: **@{info['odd']}**")
                c3.write(f"Slaagkans: {info['prob']}%")
                
                stake = c4.number_input(f"Inzet", min_value=1.0, value=10.0, key=f"s_{i}")
                if c4.button(f"Plaats", key=f"b_{i}"):
                    if st.session_state.bankroll >= stake:
                        st.session_state.bankroll -= stake
                        st.session_state.active_bets.append({
                            "Match": info['match'], "Odd": info['odd'], "Inzet": stake, 
                            "Markt": info['markt'], "Kans": f"{info['prob']}%"
                        })
                        if user_id: auto_save(user_id)
                        st.rerun()
                st.divider()

with tab2:
    st.header("📊 Actieve Portefeuille")
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))
    else: st.info("Geen actieve posities.")

with tab3:
    st.header("📉 Live Center")
    st.write("Hier worden scores getoond van je geplaatste bets.")
