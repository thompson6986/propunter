import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
import time

# --- DATABASE INITIALISATIE ---
HAS_DB = False
db = None

try:
    from google.cloud import firestore
    if "firebase" in st.secrets:
        db = firestore.Client.from_service_account_info(dict(st.secrets["firebase"]))
        HAS_DB = True
except Exception as e:
    HAS_DB = False

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "punter-pro-ultimate-v18"

st.set_page_config(page_title="ProPunter Master V18", page_icon="⚽", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 25px; border-radius: 24px; border: 1px solid #1e293b; }
    .stButton>button { width: 100%; border-radius: 14px; font-weight: 800; background-color: #4f46e5; color: white; height: 3.5em; }
    [data-testid="stMetricValue"] { color: #10b981; }
    </style>
    """, unsafe_allow_html=True)

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
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("bankroll", 1000.0), data.get("active_bets", [])
        except: pass
    return 1000.0, []

# --- SESSION STATE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []
if 'generated_slips' not in st.session_state:
    st.session_state.generated_slips = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.write("Status: " + ("✅ Cloud Verbonden" if HAS_DB else "🔌 Lokaal Mode"))
    
    user_id = st.text_input("User ID", placeholder="punter_01")
    
    col1, col2 = st.columns(2)
    if col1.button("📥 Load"):
        if user_id:
            st.session_state.bankroll, st.session_state.active_bets = load_data(user_id)
            st.rerun()
            
    if col2.button("✨ Init"):
        if user_id:
            auto_save(user_id)
            st.success("Kluis Klaar!")

    st.divider()
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")

    if st.button("🗑️ /Clear & Refund All"):
        # DE BELANGRIJKE REFUND LOGICA
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: auto_save(user_id)
        st.success(f"€{refund_total:.2f} hersteld.")
        time.sleep(1)
        st.rerun()

# --- MAIN INTERFACE ---
tab1, tab2 = st.tabs(["⚡ Generator", "📊 Dashboard"])

with tab1:
    st.header("Vier Dagelijkse Betslips")
    if st.button("🚀 GENEREER SLIPS VOOR VANDAAG"):
        with st.spinner("Data ophalen..."):
            # Voorbeeld data - in een echte API call filteren we op odds
            brussels_tz = pytz.timezone(TIMEZONE)
            now_str = datetime.now(brussels_tz).strftime('%H:%M')
            
            st.session_state.generated_slips = {
                1.5: {"match": "Arsenal vs West Ham", "tijd": "21:00", "id": 101},
                2.0: {"match": "Lazio vs Porto", "tijd": "21:00", "id": 102},
                3.0: {"match": "Athletic Bilbao vs Sevilla", "tijd": "19:00", "id": 103},
                5.0: {"match": "Gent vs Club Brugge", "tijd": "20:30", "id": 104}
            }

    if st.session_state.generated_slips:
        cols = st.columns(4)
        for i, (odd, info) in enumerate(st.session_state.generated_slips.items()):
            with cols[i]:
                st.subheader(f"Odd: {odd}")
                st.write(f"**{info['match']}**")
                st.write(f"Tijd: {info['tijd']}")
                stake = st.number_input(f"Inzet (Min. 1)", min_value=1.0, value=10.0, key=f"s_{odd}")
                if st.button(f"Plaats @{odd}", key=f"b_{odd}"):
                    if st.session_state.bankroll >= stake:
                        st.session_state.bankroll -= stake
                        st.session_state.active_bets.append({
                            "Match": info['match'], "Tijd": info['tijd'], 
                            "Inzet": stake, "Odd": odd, "Live Score": "0-0 (NS)"
                        })
                        if user_id: auto_save(user_id)
                        st.rerun()

with tab2:
    st.header("Lopende Weddenschappen")
    if st.session_state.active_bets:
        st.table(pd.DataFrame(st.session_state.active_bets))
    else:
        st.info("Geen actieve bets.")
