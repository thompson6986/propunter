import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATIE ---
st.set_page_config(page_title="ProPunter Master V18", page_icon="⚽", layout="wide")
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
        st.sidebar.error(f"⚠️ Databasefout: {e}")

# --- HELPERS ---
def auto_save(user_id):
    if HAS_DB and user_id:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc_ref.set({
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
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.write("Status: " + ("✅ Cloud Verbonden" if HAS_DB else "🔌 Lokaal Mode"))
    
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    col1, col2 = st.columns(2)
    if col1.button("📥 Laad Data"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
            
    if col2.button("✨ Initialiseer"):
        if user_id:
            auto_save(user_id)
            st.success("Kluis aangemaakt!")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")

    # DE REFUND LOGICA: Geld van open bets terug naar bankroll
    if st.button("🗑️ /Clear & Refund All"):
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund_total:.2f} teruggestort.")
        time.sleep(1)
        st.rerun()

# --- MAIN INTERFACE: DE 4 SLIPS VAN VANDAAG ---
st.header("⚡ Dagelijkse Pro Slips (26 Feb 2026)")

slips_data = [
    {"odd": 1.5, "match": "Arsenal vs West Ham", "tijd": "21:00 CET", "markt": "Home Win"},
    {"odd": 2.0, "match": "Lazio vs FC Porto", "tijd": "21:00 CET", "markt": "Over 2.5 Goals"},
    {"odd": 3.0, "match": "Athletic Bilbao vs Sevilla", "tijd": "19:00 CET", "markt": "Draw (X)"},
    {"odd": 5.0, "match": "Gent vs Club Brugge", "tijd": "20:30 CET", "markt": "X + BTS"}
]

cols = st.columns(4)
for i, slip in enumerate(slips_data):
    with cols[i]:
        st.markdown(f"### Odd: {slip['odd']}")
        st.write(f"**{slip['match']}**")
        st.caption(f"🕒 {slip['tijd']}")
        st.info(slip['markt'])
        
        stake = st.number_input(f"Inzet (Min. 1)", min_value=1.0, value=10.0, key=f"s_{i}")
        
        if st.button(f"Plaats @{slip['odd']}", key=f"b_{i}"):
            if st.session_state.bankroll >= stake:
                st.session_state.bankroll -= stake
                st.session_state.active_bets.append({
                    "Match": slip['match'],
                    "Tijd": slip['tijd'],
                    "Odd": slip['odd'],
                    "Inzet": stake,
                    "Timestamp": datetime.now(pytz.timezone(TIMEZONE)).strftime("%H:%M")
                })
                if user_id: auto_save(user_id)
                st.rerun()

st.divider()
st.subheader("📊 Lopende Portefeuille")
if st.session_state.active_bets:
    st.table(pd.DataFrame(st.session_state.active_bets))
else:
    st.info("Geen actieve posities.")
